import logging
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from pathlib import Path
from sse_starlette.sse import EventSourceResponse

from backend.database import get_db
from backend.models.user import User
from backend.models.repository import Repository, Analysis, AnalysisJob, AnalysisArtifact, TaskStatus
from backend.dependencies.auth import get_current_user
from backend.services.github import check_repo_limits, fetch_file_content
from backend.task_manager import task_manager
from backend.intelligence.graphs.graph_query_service import GraphQueryService

from pydantic import BaseModel

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent.parent

repo_router = APIRouter()

@repo_router.get("/{repo_name}/tasks")
def get_tasks(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Return current snapshot from in-memory store (fast path)
    # Falls back to DB if process was restarted and memory was cleared
    mem = task_manager.get_all(current_user.id, repo_name)
    if mem:
        return mem
    rows = db.query(TaskStatus).filter(
        TaskStatus.user_id == current_user.id,
        TaskStatus.repo_name == repo_name
    ).all()
    return {row.task_name: row.status for row in rows}


@repo_router.get("/{repo_name}/tasks/stream")
async def stream_tasks(repo_name: str, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """SSE endpoint — browser subscribes once, server pushes on every task status change."""
    
    async def event_generator():
        queue = task_manager.subscribe(current_user.id, repo_name)
        try:
            # Send current state immediately on connect so browser isn't blank
            current = task_manager.get_all(current_user.id, repo_name)
            if not current:
                # Fallback: load from DB (e.g. after backend restart)
                rows = db.query(TaskStatus).filter(
                    TaskStatus.user_id == current_user.id,
                    TaskStatus.repo_name == repo_name
                ).all()
                current = {row.task_name: row.status for row in rows}
                # Seed TaskManager with DB state so future notifies work
                for task_name, status in current.items():
                    task_manager._statuses.setdefault(
                        task_manager._key(current_user.id, repo_name), {}
                    )[task_name] = status
            
            yield {"data": json.dumps(current)}
            
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break
                
                try:
                    # Wait for next notification from background task
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {"data": payload}
                except asyncio.TimeoutError:
                    # Send a heartbeat comment to keep connection alive
                    yield {"comment": "keepalive"}
        finally:
            task_manager.unsubscribe(current_user.id, repo_name, queue)
    
    return EventSourceResponse(event_generator())

import_router = APIRouter()

class ImportRequest(BaseModel):
    url: str
    
class GraphQueryRequest(BaseModel):
    node_id: str
    direction: str = "both"
    depth: int = 1
    max_nodes: int = 50
    relationship_type: str = "calls"

class ExplainTraceRequest(BaseModel):
    feature_query: str
    trace_data: dict

# Queue setup - will be injected or accessed globally in a real app
# For now we'll import the global queue from main.py, but to avoid circular imports, 
# we'll define a helper function to enqueue
def enqueue_job(job_id: int):
    from backend.main import repo_queue
    import asyncio
    asyncio.create_task(repo_queue.enqueue(job_id))


@import_router.post("")
async def import_repo(req: ImportRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    url = req.url
    if not url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only GitHub URLs are supported.")

    parts = url.rstrip("/").split("/")
    owner = parts[-2]
    repo_name = parts[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    # Pre-flight check
    try:
        limit_data = await check_repo_limits(owner, repo_name, current_user.github_access_token)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"GitHub API error: {e}")
        raise HTTPException(status_code=500, detail="Failed to communicate with GitHub API.")

    # Check if repo exists
    repo = db.query(Repository).filter(
        Repository.user_id == current_user.id,
        Repository.github_repo_id == limit_data["github_repo_id"]
    ).first()

    if not repo:
        repo = Repository(
            github_repo_id=limit_data["github_repo_id"],
            url=url,
            default_branch=limit_data["default_branch"],
            user_id=current_user.id
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

    # Check for unfinished jobs
    unfinished = db.query(AnalysisJob).join(Analysis).filter(
        Analysis.repository_id == repo.id,
        AnalysisJob.status.in_(["Queued", "Downloading", "Analyzing", "Saving"])
    ).first()

    if unfinished:
        return {"message": "Analysis is already in progress.", "job_id": unfinished.id}

    # Create new analysis
    analysis = Analysis(repository_id=repo.id)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    job = AnalysisJob(analysis_id=analysis.id)
    db.add(job)
    db.commit()
    db.refresh(job)

    # Enqueue
    enqueue_job(job.id)

    return {"message": "Repository import queued.", "job_id": job.id, "repo": repo_name}

@repo_router.post("/{repo_name}/reanalyze")
async def reanalyze_repo(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repos = db.query(Repository).filter(Repository.user_id == current_user.id).all()
    repo = None
    for r in repos:
        if r.url.rstrip("/").endswith(f"/{repo_name}") or r.url.rstrip("/").endswith(f"/{repo_name}.git"):
            repo = r
            break
            
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Check for unfinished jobs
    unfinished = db.query(AnalysisJob).join(Analysis).filter(
        Analysis.repository_id == repo.id,
        AnalysisJob.status.in_(["Queued", "Downloading", "Analyzing", "Saving"])
    ).first()

    if unfinished:
        return {"message": "Analysis is already in progress.", "job_id": unfinished.id}

    analysis = Analysis(repository_id=repo.id)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    job = AnalysisJob(analysis_id=analysis.id)
    db.add(job)
    db.commit()
    db.refresh(job)

    enqueue_job(job.id)
    return {"message": "Reanalysis queued.", "job_id": job.id}

@repo_router.get("")
def list_repos(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repos = db.query(Repository).filter(Repository.user_id == current_user.id).all()
    results = []
    for r in repos:
        # Get latest analysis status
        latest = db.query(Analysis).filter(Analysis.repository_id == r.id).order_by(Analysis.created_at.desc()).first()
        status = latest.status if latest else "Unknown"
        
        parts = r.url.rstrip("/").split("/")
        repo_name = parts[-1]
        
        results.append({
            "id": r.id,
            "project_name": repo_name,
            "url": r.url,
            "status": status,
            "import_time": latest.created_at.isoformat() if latest else None
        })
    return {"repositories": results}

@repo_router.delete("/{repo_name}")
def delete_repo(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repos = db.query(Repository).filter(Repository.user_id == current_user.id).all()
    repo = None
    for r in repos:
        if r.url.rstrip("/").endswith(f"/{repo_name}") or r.url.rstrip("/").endswith(f"/{repo_name}.git"):
            repo = r
            break
            
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    db.delete(repo)
    db.commit()
    return {"message": "Repository deleted successfully"}

def _get_latest_analysis(repo_name: str, db: Session, current_user: User):
    # Match by URL parts
    repos = db.query(Repository).filter(Repository.user_id == current_user.id).all()
    repo = None
    for r in repos:
        if r.url.rstrip("/").endswith(f"/{repo_name}") or r.url.rstrip("/").endswith(f"/{repo_name}.git"):
            repo = r
            break
            
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
        
    latest = db.query(Analysis).filter(Analysis.repository_id == repo.id).order_by(Analysis.created_at.desc()).first()
    if not latest:
        raise HTTPException(status_code=404, detail="No analysis found for this repository")
    return repo, latest

@repo_router.get("/{repo_name}/scan")
def scan_repo(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    except HTTPException:
        return {"status": "no_analysis"}
    
    if analysis.status != "Completed":
        job = db.query(AnalysisJob).filter(AnalysisJob.analysis_id == analysis.id).first()
        job_status = job.status if job else analysis.status
        return {"status": "processing", "job_status": job_status}
        
    metrics = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "metrics").first()
    dependencies = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "dependencies").first()
    
    metrics_data = metrics.data if metrics else {}
    dep_data = dependencies.data if dependencies else {"nodes": [], "edges": []}
    
    # Reconstruct hierarchy from dep_nodes
    hierarchy = {"name": repo_name, "type": "directory", "children": []}
    files_metadata = []
    
    dirs_by_path = {}
    for node in dep_data.get("nodes", []):
        path = node["full_path"]
        parts = path.split("/")
        
        # Build dir structure
        curr_path = ""
        for i in range(len(parts) - 1):
            parent = curr_path
            curr_path = f"{curr_path}/{parts[i]}" if curr_path else parts[i]
            if curr_path not in dirs_by_path:
                d_node = {"name": parts[i], "type": "directory", "children": []}
                dirs_by_path[curr_path] = d_node
                if parent == "":
                    hierarchy["children"].append(d_node)
                else:
                    dirs_by_path[parent]["children"].append(d_node)
                    
        # Add file
        f_node = {"name": node["label"], "type": "file", "path": path}
        parent = "/".join(parts[:-1])
        if parent == "":
            hierarchy["children"].append(f_node)
        else:
            dirs_by_path[parent]["children"].append(f_node)
            
        files_metadata.append({
            "path": path,
            "extension": "." + path.split(".")[-1] if "." in path else "",
            "language": node.get("language", "Unknown"),
            "size": 0,
            "modified_time": ""
        })
        
    return {
        "overview": {
            "total_files": metrics_data.get("total_files", 0),
            "total_python_files": metrics_data.get("python_files", 0),
            "total_directories": metrics_data.get("total_directories", 0),
            "language": "Unknown"
        },
        "hierarchy": hierarchy,
        "files": files_metadata
    }

@repo_router.get("/{repo_name}/parse")
async def parse_repo_file(repo_name: str, file_path: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    
    parts = repo.url.rstrip("/").split("/")
    owner = parts[-2]
    
    # Dynamically fetch raw file content from GitHub
    source_code = await fetch_file_content(owner, repo_name, repo.default_branch, file_path, current_user.github_access_token)
    
    return {
        "source_code": source_code,
        "imports": [],
        "functions": [],
        "classes": [],
        "docstring": ""
    }

@repo_router.get("/{repo_name}/dependencies")
def get_dependencies(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    art = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "dependencies").first()
    return art.data if art else {"nodes": [], "edges": []}

@repo_router.get("/{repo_name}/call-graph")
def get_call_graph(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    art = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "call_graph").first()
    return art.data if art else {"nodes": [], "edges": []}

@repo_router.get("/{repo_name}/symbols")
def get_symbols(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    art = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "symbols").first()
    return {"symbols": art.data if art else []}

@repo_router.get("/{repo_name}/stats")
def get_stats(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    art = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "metrics").first()
    return art.data if art else {}

@repo_router.get("/{repo_name}/health/findings")
def get_health_findings(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    art = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "findings").first()
    return {"findings": art.data if art else []}

@repo_router.get("/{repo_name}/health/cycles")
def get_health_cycles(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    art = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "cycles").first()
    return {"cycles": art.data if art else []}

@repo_router.get("/{repo_name}/health/scores")
def get_health_scores(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    
    findings_art = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "findings").first()
    findings = findings_art.data if findings_art else []
    
    base_score = 100.0
    deduction = 0.0
    
    for f in findings:
        severity = f.get("severity", "INFO").upper()
        if severity in ["CRITICAL", "ERROR"]:
            deduction += 5.0
        elif severity == "WARNING":
            deduction += 2.0
        else:
            deduction += 0.5
            
    final_score = max(0.0, base_score - deduction)
    
    if final_score > 90:
        status = "Excellent"
    elif final_score > 75:
        status = "Good"
    elif final_score > 50:
        status = "Fair"
    else:
        status = "Needs Work"
        
    return {
        "health_score": round(final_score),
        "status": status,
        "categories": {
            "maintainability": {
                "score": max(0, 100 - deduction * 0.4),
                "weight": 0.4,
                "explanation": "Code maintainability based on complexity and structure."
            },
            "reliability": {
                "score": max(0, 100 - deduction * 0.3),
                "weight": 0.3,
                "explanation": "Likelihood of bugs and runtime issues."
            },
            "security": {
                "score": max(0, 100 - deduction * 0.3),
                "weight": 0.3,
                "explanation": "Security vulnerabilities and safe coding practices."
            }
        }
    }

@repo_router.get("/{repo_name}/health/metrics")
def get_health_metrics(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    art = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "metrics").first()
    return art.data if art else {}

# Stub out the rest of the missing endpoints to avoid 404s

def get_or_build_model(repo_name: str, db: Session, current_user: User):
    repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    art = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "core_model").first()
    if not art or not art.blob_data:
        raise HTTPException(status_code=404, detail="Model artifact not found")
    import pickle
    try:
        model = pickle.loads(art.blob_data)
        from backend.intelligence import QueryLayer
        return QueryLayer(model)
    except Exception as e:
        logger.error(f"Failed to unpickle model: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse model")

def get_task_status(repo_name: str, task_name: str, current_user: User, db: Session = None):
    if db is None:
        return None
    row = db.query(TaskStatus).filter(
        TaskStatus.user_id == current_user.id,
        TaskStatus.repo_name == repo_name,
        TaskStatus.task_name == task_name
    ).first()
    return row.status if row else None
    
def set_task_status(repo_name: str, task_name: str, status: str, current_user: User, db: Session = None):
    if db is None:
        return
    row = db.query(TaskStatus).filter(
        TaskStatus.user_id == current_user.id,
        TaskStatus.repo_name == repo_name,
        TaskStatus.task_name == task_name
    ).first()
    if row:
        row.status = status
        row.updated_at = datetime.now(timezone.utc)
    else:
        row = TaskStatus(
            user_id=current_user.id,
            repo_name=repo_name,
            task_name=task_name,
            status=status
        )
        db.add(row)
    db.commit()
    
    # Notify SSE subscribers instantly (no polling needed)
    task_manager.notify(current_user.id, repo_name, task_name, status)


@repo_router.get("/{repo_name}/architecture")
def get_architecture(repo_name: str, node_id: str = "root", db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, db, current_user)
    nodes = []
    
    if node_id == "root":
        for d in query_layer.get_directories():
            if str(Path(d.path).parent).replace("\\", "/") == ".":
                nodes.append({"id": d.path, "name": d.name, "type": "folder", "parent": "root", "has_children": True, "path": d.path})
        for f in query_layer.get_files():
            if str(Path(f.path).parent).replace("\\", "/") == ".":
                nodes.append({"id": f.path, "name": f.name, "type": "file", "parent": "root", "has_children": f.is_python, "path": f.path})
    elif "::" not in node_id:
        for d in query_layer.get_directories():
            if str(Path(d.path).parent).replace("\\", "/") == node_id:
                nodes.append({"id": d.path, "name": d.name, "type": "folder", "parent": node_id, "has_children": True, "path": d.path})
        for f in query_layer.get_files():
            if str(Path(f.path).parent).replace("\\", "/") == node_id:
                nodes.append({"id": f.path, "name": f.name, "type": "file", "parent": node_id, "has_children": f.is_python, "path": f.path})
        
        file_node = query_layer.get_file(node_id)
        if file_node and file_node.is_python:
            for c in query_layer.get_classes_in_file(node_id):
                nodes.append({"id": c.id, "name": c.name, "type": "class", "parent": node_id, "has_children": True, "path": node_id})
            for fn in [fn for fn in query_layer.model.entities.functions.values() if fn.file_id == node_id]:
                nodes.append({"id": fn.id, "name": fn.name, "type": "function", "parent": node_id, "has_children": False, "path": node_id})
    else:
        # It's a class
        methods = [m for m in query_layer.model.entities.methods.values() if m.class_id == node_id]
        for m in methods:
            nodes.append({"id": m.id, "name": m.name, "type": "function", "parent": node_id, "has_children": False, "path": m.file_id})
            
    return {"nodes": nodes}


@repo_router.post("/{repo_name}/index")
def index_repo(repo_name: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_status = get_task_status(repo_name, "index", current_user, db)
    if current_status == "processing":
        return {"status": "processing"}
    if current_status == "completed":
        return {"status": "completed"}
        
    set_task_status(repo_name, "index", "processing", current_user, db)
    
    def background_index():
        from backend.database import SessionLocal
        bg_db = SessionLocal()
        try:
            query_layer = get_or_build_model(repo_name, bg_db, current_user)
            set_task_status(repo_name, "index", "completed", current_user, bg_db)
        except Exception as e:
            logger.error(f"Index failed: {e}")
            set_task_status(repo_name, "index", "failed", current_user, bg_db)
        finally:
            bg_db.close()
            
    background_tasks.add_task(background_index)
    return {"status": "processing"}


@repo_router.get("/{repo_name}/search")
def search_repo(repo_name: str, q: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not q or len(q.strip()) == 0:
        return {"results": []}
    query_layer = get_or_build_model(repo_name, db, current_user)
    results = query_layer.search_entities(q)
    formatted = []
    for r in results:
        formatted.append({
            "file_path": r["file"],
            "match_reasons": [f"Matches {r['type']}: {r['name']}"]
        })
    return {"results": formatted}


@repo_router.post("/{repo_name}/symbols/index")
def index_symbols(repo_name: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_status = get_task_status(repo_name, "symbols_index", current_user, db)
    if current_status == "processing":
        return {"status": "processing"}
        
    set_task_status(repo_name, "symbols_index", "processing", current_user, db)
    
    def background_symbols_index():
        from backend.database import SessionLocal
        bg_db = SessionLocal()
        try:
            query_layer = get_or_build_model(repo_name, bg_db, current_user)
            set_task_status(repo_name, "symbols_index", "completed", current_user, bg_db)
        except Exception as e:
            logger.error(f"Symbols index failed: {e}")
            set_task_status(repo_name, "symbols_index", "failed", current_user, bg_db)
        finally:
            bg_db.close()
            
    background_tasks.add_task(background_symbols_index)
    return {"status": "processing"}


@repo_router.get("/{repo_name}/symbols/search")
def search_symbols(repo_name: str, q: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not q:
        return {"results": []}
    query_layer = get_or_build_model(repo_name, db, current_user)
    q_lower = q.lower()
    results = []
    for c in query_layer.model.entities.classes.values():
        if q_lower in c.name.lower():
            results.append({"id": c.id, "type": "Class", "name": c.name, "file_path": c.file_id, "line_number": c.line_number})
    for f in query_layer.model.entities.functions.values():
        if q_lower in f.name.lower():
            results.append({"id": f.id, "type": "Function", "name": f.name, "file_path": f.file_id, "line_number": f.line_number})
    return {"results": results}
    

@repo_router.get("/{repo_name}/summary")
def get_summary(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        repo, analysis = _get_latest_analysis(repo_name, db, current_user)
    except HTTPException:
        return {"summary": None, "outdated": False}
    
    summary_art = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "summary").first()
    
    if not summary_art:
        return {"summary": None, "outdated": False}
        
    return {"summary": summary_art.data, "outdated": False}


@repo_router.post("/{repo_name}/summary/generate")
def generate_summary(repo_name: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_status = get_task_status(repo_name, "summary", current_user, db)
    if current_status == "processing":
        return {"status": "processing"}
    
    set_task_status(repo_name, "summary", "processing", current_user, db)
    
    def background_generate_summary():
        # Get a new DB session for the background thread
        from backend.database import SessionLocal
        bg_db = SessionLocal()
        try:
            from backend.llm_service import llm_service
            query_layer = get_or_build_model(repo_name, bg_db, current_user)
            
            repo, analysis = _get_latest_analysis(repo_name, bg_db, current_user)
            em_art = bg_db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "enriched_metadata").first()
            
            if em_art and em_art.data:
                metadata = em_art.data
            else:
                # Fallback: build basic metadata from existing artifacts
                # This handles repos analyzed before RepositoryMetadataStage was added
                metrics_art = bg_db.query(AnalysisArtifact).filter(
                    AnalysisArtifact.analysis_id == analysis.id,
                    AnalysisArtifact.type == "metrics"
                ).first()
                metrics = metrics_art.data if metrics_art else {}
                
                metadata = {
                    "schema_version": 1,
                    "note": "Basic metadata only. Re-analyze the repository to generate enriched metadata.",
                    "repository": {
                        "name": repo_name,
                    },
                    "statistics": {
                        "files": metrics.get("total_files", "unknown"),
                        "python_files": metrics.get("python_files", "unknown"),
                        "directories": metrics.get("total_directories", "unknown"),
                    },
                    "modules": [
                        {"name": m.get("module", ""), "function_count": m.get("count", 0)}
                        for m in metrics.get("largest_modules", [])[:5]
                    ],
                    "frameworks": [],
                    "entrypoints": [],
                    "architecture": {"style": "unknown", "components": []},
                    "readme_summary": None
                }
            
            summary_md = llm_service.generate_summary(metadata)
            
            # Save or update summary artifact
            summary_art = bg_db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == analysis.id, AnalysisArtifact.type == "summary").first()
            if summary_art:
                summary_art.data = summary_md
            else:
                summary_art = AnalysisArtifact(analysis_id=analysis.id, type="summary", data=summary_md)
                bg_db.add(summary_art)
            bg_db.commit()
            
            set_task_status(repo_name, "summary", "completed", current_user, bg_db)
        except Exception as e:
            bg_db.rollback()
            import traceback
            logger.error(f"Summary generation failed: \n{traceback.format_exc()}")
            set_task_status(repo_name, "summary", "failed", current_user, bg_db)
        finally:
            bg_db.close()
            
    background_tasks.add_task(background_generate_summary)
    return {"status": "processing"}


@repo_router.get("/{repo_name}/semantic-status")
def semantic_status_repo(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / f"{current_user.id}_{repo_name}"
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    state_file = target_dir / "semantic_index_state.json"
    return {"has_index": state_file.exists()}


@repo_router.post("/{repo_name}/semantic-index")
def semantic_index_repo(repo_name: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    current_status = get_task_status(repo_name, "semantic_index", current_user, db)
    if current_status == "processing":
        return {"status": "processing"}
        
    set_task_status(repo_name, "semantic_index", "processing", current_user, db)
    
    def background_semantic_index():
        from backend.database import SessionLocal
        bg_db = SessionLocal()
        try:
            query_layer = get_or_build_model(repo_name, bg_db, current_user)
            target_dir = BASE_DIR / "data/repos" / f"{current_user.id}_{repo_name}"
            chroma_dir = target_dir / "chroma"
            chroma_dir.mkdir(parents=True, exist_ok=True)
            state_file = target_dir / "semantic_index_state.json"
            state = {}
            if state_file.exists():
                try:
                    import json
                    with open(state_file, "r") as f:
                        state = json.load(f)
                except Exception:
                    state = {}
            client = chromadb.PersistentClient(path=str(chroma_dir.absolute()))
            collection = client.get_or_create_collection(name="semantic_index")
            current_files = {}
            for f in query_layer.get_files():
                if f.is_python:
                    try:
                        mtime = (target_dir / f.path).stat().st_mtime
                        current_files[f.path] = mtime
                    except Exception:
                        pass
            deleted_files = set(state.keys()) - set(current_files.keys())
            modified_files = set()
            new_files = set(current_files.keys()) - set(state.keys())
            for f in current_files:
                if f in state and current_files[f] > state[f]:
                    modified_files.add(f)
            files_to_process = new_files | modified_files
            files_to_delete_chunks = deleted_files | modified_files
            status = "up to date"
            if not state:
                status = "indexed"
            elif files_to_process or files_to_delete_chunks:
                status = "updated"
            if not files_to_process and not files_to_delete_chunks:
                set_task_status(repo_name, "semantic_index", "completed", current_user, bg_db)
                return
            if files_to_delete_chunks:
                for f in files_to_delete_chunks:
                    try:
                        collection.delete(where={"file_path": f})
                    except Exception:
                        pass
            documents = []
            metadatas = []
            ids = []
            import uuid
            from backend.intelligence.parser import LanguageParser
            parser = LanguageParser()
            
            for rel_str in files_to_process:
                pf = target_dir / rel_str
                ext = pf.suffix.lower()
                if not parser.supports_extension(ext):
                    continue
                    
                try:
                    with open(pf, "r", encoding="utf-8") as f:
                        source = f.read()
                    tree, _ = parser.parse_source(source, ext)
                    parsed_entities = parser.extract_entities(tree, source, rel_str, "")
                    
                    for cls in parsed_entities.get("classes", []):
                        if cls.get("source_segment"):
                            documents.append(cls["source_segment"])
                            metadatas.append({
                                "file_path": rel_str,
                                "type": "class",
                                "name": cls["name"]
                            })
                            ids.append(str(uuid.uuid4()))
                            
                    for fn in parsed_entities.get("functions", []):
                        if fn.get("source_segment"):
                            documents.append(fn["source_segment"])
                            metadatas.append({
                                "file_path": rel_str,
                                "type": "function",
                                "name": fn["name"]
                            })
                            ids.append(str(uuid.uuid4()))
                            
                    for md in parsed_entities.get("methods", []):
                        if md.get("source_segment"):
                            documents.append(md["source_segment"])
                            metadatas.append({
                                "file_path": rel_str,
                                "type": "function",
                                "name": md["name"]
                            })
                            ids.append(str(uuid.uuid4()))
                except Exception:
                    pass
            if documents:
                batch_size = 2000
                for i in range(0, len(documents), batch_size):
                    collection.upsert(
                        documents=documents[i:i+batch_size],
                        metadatas=metadatas[i:i+batch_size],
                        ids=ids[i:i+batch_size]
                    )
            for f in deleted_files:
                if f in state:
                    del state[f]
            for f in files_to_process:
                state[f] = current_files[f]
            try:
                import json
                with open(state_file, "w") as f:
                    json.dump(state, f, indent=2)
            except Exception:
                pass
            set_task_status(repo_name, "semantic_index", "completed", current_user, bg_db)
        except Exception as e:
            logger.error(f"Semantic index failed: {e}")
            set_task_status(repo_name, "semantic_index", "failed", current_user, bg_db)
        finally:
            bg_db.close()

    background_tasks.add_task(background_semantic_index)
    return {"status": "processing"}


def get_chroma_collection(repo_name: str, current_user: User, db: Session):
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / f"{current_user.id}_{repo_name}"
    chroma_dir = target_dir / "chroma"
    
    if not chroma_dir.exists():
        repo = db.query(Repository).filter(Repository.user_id == current_user.id).filter(Repository.url.endswith(repo_name) | Repository.url.endswith(f"{repo_name}.git")).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        latest_analysis = db.query(Analysis).filter(Analysis.repository_id == repo.id).order_by(Analysis.created_at.desc()).first()
        if not latest_analysis:
            raise HTTPException(status_code=404, detail="No analysis found")
            
        semantic_artifact = db.query(AnalysisArtifact).filter(AnalysisArtifact.analysis_id == latest_analysis.id, AnalysisArtifact.type == "semantic_index_db").first()
        if not semantic_artifact or not semantic_artifact.blob_data:
            raise HTTPException(status_code=404, detail="Semantic index not found in analysis artifacts")
            
        target_dir.mkdir(parents=True, exist_ok=True)
        zip_path = target_dir / "chroma_temp.zip"
        with open(zip_path, "wb") as f:
            f.write(semantic_artifact.blob_data)
            
        import shutil
        shutil.unpack_archive(str(zip_path), str(chroma_dir), 'zip')
        
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(chroma_dir.absolute()))
        return client.get_collection(name="semantic_index")
    except Exception as e:
        logger.error(f"Failed to load Chroma collection: {e}")
        raise HTTPException(status_code=500, detail="Semantic index not found or corrupted")


@repo_router.get("/{repo_name}/semantic-search")
def semantic_search_repo(repo_name: str, q: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not q or len(q.strip()) == 0:
        return {"results": []}
        
    collection = get_chroma_collection(repo_name, current_user, db)
        
    try:
        query_results = collection.query(query_texts=[q], n_results=10)
        results = []
        if query_results and query_results["metadatas"] and len(query_results["metadatas"]) > 0:
            for idx, meta in enumerate(query_results["metadatas"][0]):
                results.append({
                    "file_path": meta["file_path"],
                    "match_type": meta["type"],
                    "match_name": meta["name"],
                    "distance": query_results["distances"][0][idx] if query_results["distances"] else 0
                })
        return {"results": results}
    except Exception as e:
        logger.error(f"Failed to search: {e}")
        raise HTTPException(status_code=500, detail="Failed to search")


@repo_router.get("/{repo_name}/graph/search")
def graph_search(repo_name: str, q: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, db, current_user)
    service = GraphQueryService(query_layer.model)
    return {"results": service.search(q)}


@repo_router.post("/{repo_name}/graph/query")
def graph_query(repo_name: str, req: GraphQueryRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, db, current_user)
    service = GraphQueryService(query_layer.model)
    result = service.traverse(
        node_id=req.node_id,
        direction=req.direction,
        depth=req.depth,
        max_nodes=req.max_nodes,
        relationship_type=req.relationship_type
    )
    return result




@repo_router.get("/{repo_name}/health/layers")
def get_health_layers(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, db, current_user)
    architecture = getattr(query_layer.model.analyses, "architecture", {})
    layers = [{"module_id": k, "layer": _serialize_dataclass(v)} for k, v in architecture.items()]
    return {"layers": layers}


@repo_router.get("/{repo_name}/health/dependencies")
def get_health_dependencies(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, db, current_user)
    dep_graph = getattr(query_layer.model.analyses, "dependency_graph", None)
    if not dep_graph:
        return {"edges": []}
    
    edges = getattr(dep_graph, "edges", None) or []
    return {"edges": _serialize_dataclass(edges)}


@repo_router.get("/{repo_name}/health/dead-code")
def get_health_dead_code(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, db, current_user)
    findings = getattr(query_layer.model.analyses, "findings", None) or []
    dead_code = [f for f in findings if "Unused" in f.title or "Unreachable" in f.title]
    return {"findings": _serialize_dataclass(dead_code)}


@repo_router.get("/{repo_name}/health/smells")
def get_health_smells(repo_name: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, db, current_user)
    cycles = getattr(query_layer.model.analyses, "cycles", None) or []
    findings = getattr(query_layer.model.analyses, "findings", None) or []
    
    smells = []
    # Add cycles as smells
    for c in cycles:
        smells.append({
            "type": "Cycle",
            "severity": _serialize_dataclass(c.severity),
            "description": c.description,
            "members": c.members
        })
        
    # Add high severity findings as smells
    from analysis.models.severity import Severity
    for f in findings:
        if f.severity in (Severity.ERROR, Severity.CRITICAL):
            smells.append({
                "type": "Finding",
                "severity": _serialize_dataclass(f.severity),
                "description": f.description,
                "file_path": f.file_path
            })
            
    return {"smells": smells}


@repo_router.get("/{repo_name}/trace")
def trace_feature(repo_name: str, q: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not q or len(q.strip()) == 0:
        return {"trace": None}
        
    try:
        collection = get_chroma_collection(repo_name, current_user, db)
        query_results = collection.query(query_texts=[q], n_results=5)
        seed_nodes = []
        if query_results and query_results.get("metadatas") and len(query_results["metadatas"]) > 0:
            # We need query_layer to resolve actual entity IDs
            try:
                query_layer = get_or_build_model(repo_name, db, current_user)
            except Exception as e:
                logger.error(f"Failed to build model for trace: {e}")
                return {"trace": None}
                
            for item in query_results["metadatas"][0]:
                fp = item.get("file_path")
                name = item.get("name")
                typ = item.get("type")
                ent_id = None
                
                if typ == "function":
                    for f in query_layer.model.entities.functions.values():
                        if getattr(f, "file_id", "") == fp and getattr(f, "name", "") == name:
                            ent_id = getattr(f, "id", None)
                            break
                elif typ == "class":
                    for c in query_layer.model.entities.classes.values():
                        if getattr(c, "file_id", "") == fp and getattr(c, "name", "") == name:
                            ent_id = getattr(c, "id", None)
                            break
                            
                if ent_id:
                    item["id"] = ent_id
                    seed_nodes.append(item)
    except Exception as e:
        logger.error(f"Semantic search failed for trace: {e}")
        seed_nodes = []
        
    if not seed_nodes:
        return {"trace": None}
        
    # Get repository model
    # In main.py there is get_or_build_model
    # Let's see how get_or_build_model is defined in main.py... oh it's query_layer = get_or_build_model(repo_name, db, current_user)
    try:
        query_layer = get_or_build_model(repo_name, db, current_user)
    except Exception as e:
        logger.error(f"Failed to build model for trace: {e}")
        return {"trace": None}
    
    from backend.intelligence.feature_tracing import DeterministicTracer
    tracer = DeterministicTracer(query_layer.model)
    trace_result = tracer.trace_feature(seed_nodes)
    
    return {"trace": trace_result}


@repo_router.post("/{repo_name}/trace/explain")
def explain_trace(repo_name: str, req: ExplainTraceRequest):
    prompt = f"Explain the following implementation trace for the feature '{req.feature_query}'. The trace was deterministically generated from the repository's semantic, dependency, and call graphs. Do not add any new nodes or hallucinate execution paths. Explain what each component does in the context of the flow.\n\nTrace Data: {json.dumps(req.trace_data, indent=2)}"
    
    try:
        explanation = llm_service.generate_explanation(prompt)
        return {"explanation": explanation}
    except Exception as e:
        logger.error(f"Explanation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate explanation")

