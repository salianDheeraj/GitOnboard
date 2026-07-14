from fastapi import FastAPI, HTTPException, APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import BackgroundTasks
import subprocess
import os
import shutil
from pathlib import Path
import logging

import json
from datetime import datetime, timezone
import ast
import chromadb
from backend.llm_service import llm_service

from backend.config import settings
from backend.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Repository Intelligence Platform API (MVP)",
    version="0.1.0"
)

# Auto-create database tables
from backend.database import engine, Base
from backend.models.user import User
Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from backend.routers import auth_router, health_router
from backend.dependencies.auth import get_current_user

app.include_router(auth_router, prefix="/api")
app.include_router(health_router, prefix="/api")

repo_router = APIRouter(prefix="/api/repos", dependencies=[Depends(get_current_user)])
import_router = APIRouter(prefix="/api/import", dependencies=[Depends(get_current_user)])



class ImportRequest(BaseModel):
    url: str

BASE_DIR = Path(__file__).parent.parent.absolute()
METADATA_FILE = BASE_DIR / "data/repos_metadata.json"

def load_metadata():
    if METADATA_FILE.exists():
        with open(METADATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_metadata(data):
    with open(METADATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_task_status(repo_name: str, task_name: str, current_user: User):
    task_file = BASE_DIR / "data" / "repos" / f"{current_user.id}_{repo_name}" / ".tasks.json"
    if not task_file.exists():
        return None
    try:
        import json
        with open(task_file, "r") as f:
            tasks = json.load(f)
        return tasks.get(task_name)
    except:
        return None

def set_task_status(repo_name: str, task_name: str, status: str, current_user: User):
    task_file = BASE_DIR / "data" / "repos" / f"{current_user.id}_{repo_name}" / ".tasks.json"
    try:
        import json
        tasks = {}
        if task_file.exists():
            with open(task_file, "r") as f:
                tasks = json.load(f)
        if status is None:
            tasks.pop(task_name, None)
        else:
            tasks[task_name] = status
        with open(task_file, "w") as f:
            json.dump(tasks, f)
    except Exception as e:
        logger.error(f"Failed to set task status: {e}")

@repo_router.get("/{repo_name}/tasks")
def get_tasks(repo_name: str, current_user: User = Depends(get_current_user)):
    task_file = BASE_DIR / "data" / "repos" / f"{current_user.id}_{repo_name}" / ".tasks.json"
    tasks = {}
    if task_file.exists():
        try:
            import json
            with open(task_file, "r") as f:
                tasks = json.load(f)
        except:
            pass
    return tasks

@app.get("/")
def read_root():
    return {"message": "Welcome to Repository Intelligence Platform API"}

from backend.models.user import User

@import_router.post("")
def import_repo(req: ImportRequest, current_user: User = Depends(get_current_user)):
    repo_url = req.url
    if not repo_url.startswith("https://github.com/"):
        logger.warning(f"Invalid repository URL attempted: {repo_url}")
        raise HTTPException(status_code=400, detail="Only GitHub URLs are supported.")

    repo_name = repo_url.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    # Store in data/repos
    repos_dir = BASE_DIR / "data/repos"
    repos_dir.mkdir(parents=True, exist_ok=True)
    
    # Isolate by user
    target_dir = repos_dir / f"{current_user.id}_{repo_name}"
    
    if target_dir.exists():
        logger.info(f"Repository {repo_name} already exists for user {current_user.id}.")
        return {"message": f"Repository {repo_name} already imported.", "repo": repo_name}

    logger.info(f"Cloning repository {repo_url} into {target_dir}")
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    
    # Use authenticated clone URL if we have an access token
    clone_url = repo_url
    if current_user.github_access_token:
        # e.g. https://<token>@github.com/owner/repo
        clone_url = repo_url.replace("https://", f"https://oauth2:{current_user.github_access_token}@")

    try:
        result = subprocess.run(
            ["git", "clone", "-c", "core.longpaths=true", clone_url, str(target_dir)],
            capture_output=True,
            text=True,
            env=env
        )
        if result.returncode != 0:
            logger.error(f"Failed to clone repository: {result.stderr}")
            if "Authentication failed" in result.stderr or "not found" in result.stderr.lower():
                raise HTTPException(status_code=400, detail="Failed to clone repository. It may not exist, or you lack permissions to access it.")
            else:
                raise HTTPException(status_code=500, detail=f"Failed to clone repository: {result.stderr}")
        
        logger.info(f"Successfully cloned {repo_name}")
        
        # Phase 1 constraint: Ignore directories during processing (by removing them)
        ignored_dirs = [".git", "node_modules", "venv", "build", "dist", "__pycache__"]
        for d in ignored_dirs:
            p = target_dir / d
            if p.exists() and p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
                logger.info(f"Removed ignored directory: {p}")
        
        # Save metadata
        from collections import Counter
        from backend.intelligence.parser import LanguageParser
        
        parser = LanguageParser()
        
        # Calculate primary language
        exts = [p.suffix.lower() for p in target_dir.rglob("*") if p.is_file()]
        supported_exts = [ext for ext in exts if parser.supports_extension(ext)]
        
        if supported_exts:
            most_common = Counter(supported_exts).most_common(1)[0][0]
            lang_map = {
                ".py": "Python", 
                ".js": "JavaScript", 
                ".ts": "TypeScript", 
                ".jsx": "React", 
                ".tsx": "React", 
                ".java": "Java"
            }
            primary_language = lang_map.get(most_common, "Unknown")
        else:
            primary_language = "Unknown"
            
        metadata = load_metadata()
        metadata_key = f"{current_user.id}_{repo_name}"
        metadata[metadata_key] = {
            "project_name": repo_name,
            "repository_path": str(target_dir),
            "language": primary_language,
            "import_time": datetime.now(timezone.utc).isoformat(),
            "user_id": current_user.id
        }
        save_metadata(metadata)
        
        return {"message": "Repository imported successfully", "repo": repo_name}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Failed to process repository: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process repository: {str(e)}")

@repo_router.get("")
def list_repos(current_user: User = Depends(get_current_user)):
    metadata = load_metadata()
    # Filter metadata to only return repos owned by the current user
    user_repos = [repo for repo in metadata.values() if repo.get("user_id") == current_user.id]
    return {"repositories": user_repos}

@repo_router.delete("/{repo_name}")
def delete_repo(repo_name: str, current_user: User = Depends(get_current_user)):
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / f"{current_user.id}_{repo_name}"
    metadata_key = f"{current_user.id}_{repo_name}"
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    try:
        shutil.rmtree(target_dir, ignore_errors=True)
        metadata = load_metadata()
        if metadata_key in metadata:
            del metadata[metadata_key]
            save_metadata(metadata)
            
        logger.info(f"Deleted repository {repo_name} for user {current_user.id}")
        return {"message": "Repository deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete repository {repo_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete repository")

from backend.intelligence import (
    RepositoryBuilder, RelationshipBuilder, AnalysisPipeline, QueryLayer
)
from backend.intelligence.stages.metrics_stage import MetricsStage
from backend.intelligence.graphs.call_graph import CallGraphView
from backend.intelligence.graphs.dependency_graph import DependencyGraphView
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from analysis.registry import AnalyzerRegistry
from analysis.runner import AnalysisRunner

_model_cache = {}

def get_or_build_model(repo_name: str, current_user: User) -> QueryLayer:
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / f"{current_user.id}_{repo_name}"
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    try:
        current_fingerprint = str(target_dir.stat().st_mtime)
    except Exception:
        current_fingerprint = "0"
        
    if f"{current_user.id}_{repo_name}" in _model_cache:
        cached_query = _model_cache[f"{current_user.id}_{repo_name}"]
        if cached_query.model.metadata.repository_fingerprint == current_fingerprint:
            return cached_query

    logger.info(f"Building intelligence model for {repo_name}...")
    builder = RepositoryBuilder(repo_name, target_dir)
    rel_builder = RelationshipBuilder(target_dir)
    pipeline = AnalysisPipeline(builder, rel_builder)
    pipeline.add_stage(MetricsStage())
    
    model = pipeline.run()
    
    # Phase 2 Analyzers
    registry = AnalyzerRegistry()
    registry.discover("analysis.plugins")
    
    runner = AnalysisRunner(registry)
    report = runner.run(model)
    model.analyses.findings = report.overall_findings
    
    query_layer = QueryLayer(model)
    _model_cache[f"{current_user.id}_{repo_name}"] = query_layer
    return query_layer

@repo_router.get("/{repo_name}/scan")
def scan_repo(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    metrics = query_layer.model.analyses.metrics
    
    metadata = load_metadata()
    repo_meta = metadata.get(repo_name, {})
    repo_language = repo_meta.get("language", "Unknown")
    
    hierarchy = {
        "name": repo_name,
        "type": "directory",
        "children": []
    }
    
    # Simple hierarchy builder for MVP
    dirs_by_path = {}
    for d_node in query_layer.get_directories():
        dirs_by_path[d_node.path] = {"name": d_node.name, "type": "directory", "children": []}
        
    for f in query_layer.get_files():
        parent_dir = str(Path(f.path).parent).replace("\\", "/")
        if parent_dir == ".":
            hierarchy["children"].append({"name": f.name, "type": "file", "path": f.path})
        else:
            if parent_dir in dirs_by_path:
                dirs_by_path[parent_dir]["children"].append({"name": f.name, "type": "file", "path": f.path})
                
    for d_path, d_dict in dirs_by_path.items():
        parent_dir = str(Path(d_path).parent).replace("\\", "/")
        if parent_dir == ".":
            hierarchy["children"].append(d_dict)
        elif parent_dir in dirs_by_path:
            dirs_by_path[parent_dir]["children"].append(d_dict)
            
    files_metadata = []
    
    from backend.intelligence.parser import LanguageParser
    parser = LanguageParser()
    lang_map = {
        ".py": "Python", 
        ".js": "JavaScript", 
        ".ts": "TypeScript", 
        ".jsx": "React", 
        ".tsx": "React", 
        ".java": "Java"
    }
    
    for f in query_layer.get_files():
        lang = lang_map.get(f.extension.lower(), "Unknown")
        if not parser.supports_extension(f.extension.lower()):
            lang = "Unknown"
            
        files_metadata.append({
            "path": f.path,
            "extension": f.extension,
            "language": lang,
            "size": f.size,
            "modified_time": ""
        })
        
    return {
        "overview": {
            "total_files": metrics.get("total_files", 0),
            "total_python_files": metrics.get("python_files", 0),
            "total_directories": metrics.get("total_directories", 0),
            "language": repo_language
        },
        "hierarchy": hierarchy,
        "files": files_metadata
    }

@repo_router.get("/{repo_name}/parse")
def parse_repo_file(repo_name: str, file_path: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    
    file_node = query_layer.get_file(file_path)
    if not file_node:
        raise HTTPException(status_code=404, detail="File not found in model")
        
    classes = query_layer.get_classes_in_file(file_node.id)
    functions = [fn for fn in query_layer.model.entities.functions.values() if fn.file_id == file_node.id]
    imports = [imp for imp in query_layer.model.entities.imports.values() if imp.file_id == file_node.id]
    
    result = {
        "imports": [{"module_name": imp.module_name, "alias": imp.alias} for imp in imports],
        "functions": [{"name": f.name, "docstring": f.docstring, "line_number": f.line_number, "parameters": f.parameters} for f in functions],
        "classes": [{"name": c.name, "docstring": c.docstring, "methods": [{"name": m.name, "docstring": m.docstring} for m in query_layer.model.entities.methods.values() if m.class_id == c.id]} for c in classes],
        "docstring": ""
    }
    return result

@repo_router.get("/{repo_name}/dependencies")
def get_dependencies(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    dep_graph = DependencyGraphView(query_layer.model)
    
    from backend.intelligence.parser import LanguageParser
    parser = LanguageParser()
    lang_map = {
        ".py": "Python", 
        ".js": "JavaScript", 
        ".ts": "TypeScript", 
        ".jsx": "React", 
        ".tsx": "React", 
        ".java": "Java"
    }
    
    # Return all supported files as nodes
    nodes = []
    for f in query_layer.get_files():
        ext = f.extension.lower()
        if parser.supports_extension(ext):
            nodes.append({
                "id": f.path, 
                "label": f.name, 
                "full_path": f.path,
                "language": lang_map.get(ext, "Unknown")
            })
            
    edges = [{"id": f"e-{s}-{t}", "source": s, "target": t} for s, targets in dep_graph.get_edges().items() for t in targets]
    
    return {"nodes": nodes, "edges": edges}

@repo_router.get("/{repo_name}/call-graph")
def get_call_graph(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    call_graph = CallGraphView(query_layer.model)
    
    nodes = [{"id": n, "label": n.split('::')[-1], "full_name": n} for n in call_graph.get_nodes()]
    edges = [{"id": f"e-{s}-{t}", "source": s, "target": t} for s, targets in call_graph.get_edges().items() for t in targets]
    
    return {"nodes": nodes, "edges": edges}

@repo_router.get("/{repo_name}/architecture")
def get_architecture(repo_name: str, node_id: str = "root", current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
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
def index_repo(repo_name: str, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)):
    current_status = get_task_status(repo_name, "index", current_user)
    if current_status == "processing":
        return {"status": "processing"}
        
    set_task_status(repo_name, "index", "processing", current_user)
    
    def background_index():
        try:
            query_layer = get_or_build_model(repo_name, current_user)
            set_task_status(repo_name, "index", "completed", current_user)
        except Exception as e:
            logger.error(f"Index failed: {e}")
            set_task_status(repo_name, "index", "failed", current_user)
            
    background_tasks.add_task(background_index)
    return {"status": "processing"}

@repo_router.get("/{repo_name}/search")
def search_repo(repo_name: str, q: str, current_user: User = Depends(get_current_user)):
    if not q or len(q.strip()) == 0:
        return {"results": []}
    query_layer = get_or_build_model(repo_name, current_user)
    results = query_layer.search_entities(q)
    formatted = []
    for r in results:
        formatted.append({
            "file_path": r["file"],
            "match_reasons": [f"Matches {r['type']}: {r['name']}"]
        })
    return {"results": formatted}

@repo_router.post("/{repo_name}/symbols/index")
def index_symbols(repo_name: str, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)):
    current_status = get_task_status(repo_name, "symbols_index", current_user)
    if current_status == "processing":
        return {"status": "processing"}
        
    set_task_status(repo_name, "symbols_index", "processing", current_user)
    
    def background_symbols_index():
        try:
            query_layer = get_or_build_model(repo_name, current_user)
            set_task_status(repo_name, "symbols_index", "completed", current_user)
        except Exception as e:
            logger.error(f"Symbols index failed: {e}")
            set_task_status(repo_name, "symbols_index", "failed", current_user)
            
    background_tasks.add_task(background_symbols_index)
    return {"status": "processing"}

@repo_router.get("/{repo_name}/symbols")
def get_symbols(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    symbols = []
    for c in query_layer.model.entities.classes.values():
        symbols.append({"id": c.id, "type": "Class", "name": c.name, "file_path": c.file_id, "line_number": c.line_number, "docstring": c.docstring})
    for f in query_layer.model.entities.functions.values():
        symbols.append({"id": f.id, "type": "Function", "name": f.name, "file_path": f.file_id, "line_number": f.line_number, "docstring": f.docstring})
    for m in query_layer.model.entities.methods.values():
        symbols.append({"id": m.id, "type": "Method", "name": m.name, "file_path": m.file_id, "line_number": m.line_number, "docstring": m.docstring})
    return {"symbols": symbols}

@repo_router.get("/{repo_name}/symbols/search")
def search_symbols(repo_name: str, q: str, current_user: User = Depends(get_current_user)):
    if not q:
        return {"results": []}
    query_layer = get_or_build_model(repo_name, current_user)
    q_lower = q.lower()
    results = []
    for c in query_layer.model.entities.classes.values():
        if q_lower in c.name.lower():
            results.append({"id": c.id, "type": "Class", "name": c.name, "file_path": c.file_id, "line_number": c.line_number})
    for f in query_layer.model.entities.functions.values():
        if q_lower in f.name.lower():
            results.append({"id": f.id, "type": "Function", "name": f.name, "file_path": f.file_id, "line_number": f.line_number})
    return {"results": results}
    
@repo_router.get("/{repo_name}/stats")
def get_stats(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    return query_layer.model.analyses.metrics

@repo_router.get("/{repo_name}/summary")
def get_summary(repo_name: str, current_user: User = Depends(get_current_user)):
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / f"{current_user.id}_{repo_name}"
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    summary_file = target_dir / "summary.md"
    state_file = target_dir / "semantic_index_state.json"
    
    if not summary_file.exists():
        return {"summary": None, "outdated": False}
        
    try:
        with open(summary_file, "r", encoding="utf-8") as f:
            summary_md = f.read()
            
        outdated = False
        if state_file.exists():
            summary_mtime = summary_file.stat().st_mtime
            state_mtime = state_file.stat().st_mtime
            if state_mtime > summary_mtime:
                outdated = True
                
        return {"summary": summary_md, "outdated": outdated}
    except Exception as e:
        logger.error(f"Failed to read summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to read summary")

@repo_router.post("/{repo_name}/summary/generate")
def generate_summary(repo_name: str, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)):
    current_status = get_task_status(repo_name, "summary", current_user)
    if current_status == "processing":
        return {"status": "processing"}
    
    set_task_status(repo_name, "summary", "processing", current_user)
    
    def background_generate_summary():
        try:
            repos_dir = BASE_DIR / "data/repos"
            target_dir = repos_dir / f"{current_user.id}_{repo_name}"
            query_layer = get_or_build_model(repo_name, current_user)
            metrics = query_layer.model.analyses.metrics
            metadata = {
                "name": repo_name,
                "total_files": metrics.get("total_files", 0),
                "python_files": metrics.get("python_files", 0),
                "total_directories": metrics.get("total_directories", 0),
                "top_modules": []
            }
            summary_md = llm_service.generate_summary(metadata)
            summary_file = target_dir / "summary.md"
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write(summary_md)
            set_task_status(repo_name, "summary", "completed", current_user)
        except Exception as e:
            import traceback
            logger.error(f"Summary generation failed: \\n{traceback.format_exc()}")
            set_task_status(repo_name, "summary", "failed", current_user)
            
    background_tasks.add_task(background_generate_summary)
    return {"status": "processing"}

@repo_router.get("/{repo_name}/semantic-status")
def semantic_status_repo(repo_name: str, current_user: User = Depends(get_current_user)):
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / f"{current_user.id}_{repo_name}"
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    state_file = target_dir / "semantic_index_state.json"
    return {"has_index": state_file.exists()}

@repo_router.post("/{repo_name}/semantic-index")
def semantic_index_repo(repo_name: str, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)):
    current_status = get_task_status(repo_name, "semantic_index", current_user)
    if current_status == "processing":
        return {"status": "processing"}
        
    set_task_status(repo_name, "semantic_index", "processing", current_user)
    
    def background_semantic_index():
        try:
            query_layer = get_or_build_model(repo_name, current_user)
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
                set_task_status(repo_name, "semantic_index", "completed", current_user)
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
            set_task_status(repo_name, "semantic_index", "completed", current_user)
        except Exception as e:
            logger.error(f"Semantic index failed: {e}")
            set_task_status(repo_name, "semantic_index", "failed", current_user)

    background_tasks.add_task(background_semantic_index)
    return {"status": "processing"}

@repo_router.get("/{repo_name}/semantic-search")
def semantic_search_repo(repo_name: str, q: str, current_user: User = Depends(get_current_user)):
    if not q or len(q.strip()) == 0:
        return {"results": []}
        
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / f"{current_user.id}_{repo_name}"
    chroma_dir = target_dir / "chroma"
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    if not chroma_dir.exists():
        semantic_index_repo(repo_name)
        
    try:
        client = chromadb.PersistentClient(path=str(chroma_dir.absolute()))
        collection = client.get_collection(name="semantic_index")
    except Exception as e:
        logger.error(f"Failed to load Chroma collection: {e}")
        raise HTTPException(status_code=500, detail="Semantic index not found or corrupted")
        
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

from backend.intelligence.graphs.graph_query_service import GraphQueryService
from pydantic import BaseModel
from fastapi import BackgroundTasks

class GraphQueryRequest(BaseModel):
    node_id: str
    direction: str = "both"
    depth: int = 1
    max_nodes: int = 50
    relationship_type: str = "calls"

@repo_router.get("/{repo_name}/graph/search")
def graph_search(repo_name: str, q: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    service = GraphQueryService(query_layer.model)
    return {"results": service.search(q)}

@repo_router.post("/{repo_name}/graph/query")
def graph_query(repo_name: str, req: GraphQueryRequest, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    service = GraphQueryService(query_layer.model)
    result = service.traverse(
        node_id=req.node_id,
        direction=req.direction,
        depth=req.depth,
        max_nodes=req.max_nodes,
        relationship_type=req.relationship_type
    )
    return result



# Dashboard API Endpoints


import dataclasses
from enum import Enum

def _serialize_dataclass(obj):
    if dataclasses.is_dataclass(obj):
        return {k: _serialize_dataclass(v) for k, v in dataclasses.asdict(obj).items()}
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, dict):
        return {k: _serialize_dataclass(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_dataclass(v) for v in obj]
    return obj

@repo_router.get("/{repo_name}/health/scores")
def get_health_scores(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    health = getattr(query_layer.model.analyses, "health", None)
    if not health:
        raise HTTPException(status_code=404, detail="Health scores not found")
    return _serialize_dataclass(health)

@repo_router.get("/{repo_name}/health/metrics")
def get_health_metrics(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    metrics = getattr(query_layer.model.analyses, "metrics", None)
    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")
    return _serialize_dataclass(metrics)

@repo_router.get("/{repo_name}/health/findings")
def get_health_findings(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    findings = getattr(query_layer.model.analyses, "findings", [])
    return {"findings": _serialize_dataclass(findings)}

@repo_router.get("/{repo_name}/health/layers")
def get_health_layers(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    architecture = getattr(query_layer.model.analyses, "architecture", {})
    layers = [{"module_id": k, "layer": _serialize_dataclass(v)} for k, v in architecture.items()]
    return {"layers": layers}

@repo_router.get("/{repo_name}/health/dependencies")
def get_health_dependencies(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    dep_graph = getattr(query_layer.model.analyses, "dependency_graph", None)
    if not dep_graph:
        return {"edges": []}
    
    edges = getattr(dep_graph, "edges", None) or []
    return {"edges": _serialize_dataclass(edges)}

@repo_router.get("/{repo_name}/health/cycles")
def get_health_cycles(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    cycles = getattr(query_layer.model.analyses, "cycles", None) or []
    return {"cycles": _serialize_dataclass(cycles)}

@repo_router.get("/{repo_name}/health/dead-code")
def get_health_dead_code(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
    findings = getattr(query_layer.model.analyses, "findings", None) or []
    dead_code = [f for f in findings if "Unused" in f.title or "Unreachable" in f.title]
    return {"findings": _serialize_dataclass(dead_code)}

@repo_router.get("/{repo_name}/health/smells")
def get_health_smells(repo_name: str, current_user: User = Depends(get_current_user)):
    query_layer = get_or_build_model(repo_name, current_user)
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

# --- Phase 3: Feature Tracing ---
@repo_router.get("/{repo_name}/trace")
def trace_feature(repo_name: str, q: str):
    if not q or len(q.strip()) == 0:
        return {"trace": None}
        
    # Stage 1: Semantic search
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / f"{current_user.id}_{repo_name}"
    chroma_dir = target_dir / "chroma"
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    try:
        client = chromadb.PersistentClient(path=str(chroma_dir.absolute()))
        collection = client.get_collection(name="semantic_index")
        query_results = collection.query(query_texts=[q], n_results=5)
        seed_nodes = []
        if query_results and query_results.get("metadatas") and len(query_results["metadatas"]) > 0:
            # We need query_layer to resolve actual entity IDs
            try:
                query_layer = get_or_build_model(repo_name, current_user)
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
    # Let's see how get_or_build_model is defined in main.py... oh it's query_layer = get_or_build_model(repo_name, current_user)
    try:
        query_layer = get_or_build_model(repo_name, current_user)
    except Exception as e:
        logger.error(f"Failed to build model for trace: {e}")
        return {"trace": None}
    
    from backend.intelligence.feature_tracing import DeterministicTracer
    tracer = DeterministicTracer(query_layer.model)
    trace_result = tracer.trace_feature(seed_nodes)
    
    return {"trace": trace_result}

class ExplainTraceRequest(BaseModel):
    feature_query: str
    trace_data: dict

@repo_router.post("/{repo_name}/trace/explain")
def explain_trace(repo_name: str, req: ExplainTraceRequest):
    prompt = f"Explain the following implementation trace for the feature '{req.feature_query}'. The trace was deterministically generated from the repository's semantic, dependency, and call graphs. Do not add any new nodes or hallucinate execution paths. Explain what each component does in the context of the flow.\n\nTrace Data: {json.dumps(req.trace_data, indent=2)}"
    
    try:
        explanation = llm_service.generate_explanation(prompt)
        return {"explanation": explanation}
    except Exception as e:
        logger.error(f"Explanation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate explanation")

app.include_router(repo_router)
app.include_router(import_router)
