from fastapi import FastAPI, HTTPException
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def get_task_status(repo_name: str, task_name: str):
    task_file = BASE_DIR / "data" / "repos" / repo_name / ".tasks.json"
    if not task_file.exists():
        return None
    try:
        import json
        with open(task_file, "r") as f:
            tasks = json.load(f)
        return tasks.get(task_name)
    except:
        return None

def set_task_status(repo_name: str, task_name: str, status: str):
    task_file = BASE_DIR / "data" / "repos" / repo_name / ".tasks.json"
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

@app.get("/api/repos/{repo_name}/tasks")
def get_tasks(repo_name: str):
    task_file = BASE_DIR / "data" / "repos" / repo_name / ".tasks.json"
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

@app.post("/api/import")
def import_repo(req: ImportRequest):
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
    
    target_dir = repos_dir / repo_name
    
    if target_dir.exists():
        logger.info(f"Repository {repo_name} already exists.")
        return {"message": f"Repository {repo_name} already imported.", "repo": repo_name}

    logger.info(f"Cloning repository {repo_url} into {target_dir}")
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    
    try:
        result = subprocess.run(
            ["git", "clone", "-c", "core.longpaths=true", repo_url, str(target_dir)],
            capture_output=True,
            text=True,
            env=env
        )
        if result.returncode != 0:
            if "Clone succeeded, but checkout failed" in result.stderr or "Clone succeeded, but checkout failed" in result.stdout:
                logger.warning(f"Clone succeeded with checkout errors: {result.stderr}")
            else:
                logger.error(f"Failed to clone repository: {result.stderr}")
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
        metadata = load_metadata()
        metadata[repo_name] = {
            "project_name": repo_name,
            "repository_path": str(target_dir),
            "language": "Python",
            "import_time": datetime.now(timezone.utc).isoformat()
        }
        save_metadata(metadata)
        
        return {"message": "Repository imported successfully", "repo": repo_name}
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Failed to process repository: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process repository: {str(e)}")

@app.get("/api/repos")
def list_repos():
    metadata = load_metadata()
    return {"repositories": list(metadata.values())}

@app.delete("/api/repos/{repo_name}")
def delete_repo(repo_name: str):
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / repo_name
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    try:
        shutil.rmtree(target_dir, ignore_errors=True)
        metadata = load_metadata()
        if repo_name in metadata:
            del metadata[repo_name]
            save_metadata(metadata)
            
        logger.info(f"Deleted repository {repo_name}")
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

def get_or_build_model(repo_name: str) -> QueryLayer:
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / repo_name
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    try:
        current_fingerprint = str(target_dir.stat().st_mtime)
    except Exception:
        current_fingerprint = "0"
        
    if repo_name in _model_cache:
        cached_query = _model_cache[repo_name]
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
    _model_cache[repo_name] = query_layer
    return query_layer

@app.get("/api/repos/{repo_name}/scan")
def scan_repo(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    metrics = query_layer.model.analyses.metrics
    
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
    for f in query_layer.get_files():
        files_metadata.append({
            "path": f.path,
            "extension": f.extension,
            "language": "Python" if f.is_python else "Unknown",
            "size": f.size,
            "modified_time": ""
        })
        
    return {
        "overview": {
            "total_files": metrics.get("total_files", 0),
            "total_python_files": metrics.get("python_files", 0),
            "total_directories": metrics.get("total_directories", 0)
        },
        "hierarchy": hierarchy,
        "files": files_metadata
    }

@app.get("/api/repos/{repo_name}/parse")
def parse_repo_file(repo_name: str, file_path: str):
    query_layer = get_or_build_model(repo_name)
    
    file_node = query_layer.get_file(file_path)
    if not file_node:
        raise HTTPException(status_code=404, detail="File not found in model")
        
    classes = query_layer.get_classes_in_file(file_path)
    functions = [fn for fn in query_layer.model.entities.functions.values() if fn.file_id == file_path]
    
    result = {
        "imports": [],
        "functions": [{"name": f.name, "docstring": f.docstring, "line_number": f.line_number, "parameters": f.parameters} for f in functions],
        "classes": [{"name": c.name, "docstring": c.docstring, "methods": [{"name": m.name, "docstring": m.docstring} for m in query_layer.model.entities.methods.values() if m.class_id == c.id]} for c in classes],
        "docstring": ""
    }
    return result

@app.get("/api/repos/{repo_name}/dependencies")
def get_dependencies(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    dep_graph = DependencyGraphView(query_layer.model)
    
    # Return all python files as nodes, even if they have no edges
    nodes = [{"id": f.path, "label": f.name, "full_path": f.path} for f in query_layer.get_files() if f.is_python]
    
    edges = [{"id": f"e-{s}-{t}", "source": s, "target": t} for s, targets in dep_graph.get_edges().items() for t in targets]
    
    return {"nodes": nodes, "edges": edges}

@app.get("/api/repos/{repo_name}/call-graph")
def get_call_graph(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    call_graph = CallGraphView(query_layer.model)
    
    nodes = [{"id": n, "label": n.split('::')[-1], "full_name": n} for n in call_graph.get_nodes()]
    edges = [{"id": f"e-{s}-{t}", "source": s, "target": t} for s, targets in call_graph.get_edges().items() for t in targets]
    
    return {"nodes": nodes, "edges": edges}

@app.get("/api/repos/{repo_name}/architecture")
def get_architecture(repo_name: str, node_id: str = "root"):
    query_layer = get_or_build_model(repo_name)
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

@app.post("/api/repos/{repo_name}/index")
def index_repo(repo_name: str, background_tasks: BackgroundTasks):
    current_status = get_task_status(repo_name, "index")
    if current_status == "processing":
        return {"status": "processing"}
        
    set_task_status(repo_name, "index", "processing")
    
    def background_index():
        try:
            query_layer = get_or_build_model(repo_name)
            set_task_status(repo_name, "index", "completed")
        except Exception as e:
            logger.error(f"Index failed: {e}")
            set_task_status(repo_name, "index", "failed")
            
    background_tasks.add_task(background_index)
    return {"status": "processing"}

@app.get("/api/repos/{repo_name}/search")
def search_repo(repo_name: str, q: str):
    if not q or len(q.strip()) == 0:
        return {"results": []}
    query_layer = get_or_build_model(repo_name)
    results = query_layer.search_entities(q)
    formatted = []
    for r in results:
        formatted.append({
            "file_path": r["file"],
            "match_reasons": [f"Matches {r['type']}: {r['name']}"]
        })
    return {"results": formatted}

@app.post("/api/repos/{repo_name}/symbols/index")
def index_symbols(repo_name: str, background_tasks: BackgroundTasks):
    current_status = get_task_status(repo_name, "symbols_index")
    if current_status == "processing":
        return {"status": "processing"}
        
    set_task_status(repo_name, "symbols_index", "processing")
    
    def background_symbols_index():
        try:
            query_layer = get_or_build_model(repo_name)
            set_task_status(repo_name, "symbols_index", "completed")
        except Exception as e:
            logger.error(f"Symbols index failed: {e}")
            set_task_status(repo_name, "symbols_index", "failed")
            
    background_tasks.add_task(background_symbols_index)
    return {"status": "processing"}

@app.get("/api/repos/{repo_name}/symbols")
def get_symbols(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    symbols = []
    for c in query_layer.model.entities.classes.values():
        symbols.append({"id": c.id, "type": "Class", "name": c.name, "file_path": c.file_id, "line_number": c.line_number, "docstring": c.docstring})
    for f in query_layer.model.entities.functions.values():
        symbols.append({"id": f.id, "type": "Function", "name": f.name, "file_path": f.file_id, "line_number": f.line_number, "docstring": f.docstring})
    for m in query_layer.model.entities.methods.values():
        symbols.append({"id": m.id, "type": "Method", "name": m.name, "file_path": m.file_id, "line_number": m.line_number, "docstring": m.docstring})
    return {"symbols": symbols}

@app.get("/api/repos/{repo_name}/symbols/search")
def search_symbols(repo_name: str, q: str):
    if not q:
        return {"results": []}
    query_layer = get_or_build_model(repo_name)
    q_lower = q.lower()
    results = []
    for c in query_layer.model.entities.classes.values():
        if q_lower in c.name.lower():
            results.append({"id": c.id, "type": "Class", "name": c.name, "file_path": c.file_id, "line_number": c.line_number})
    for f in query_layer.model.entities.functions.values():
        if q_lower in f.name.lower():
            results.append({"id": f.id, "type": "Function", "name": f.name, "file_path": f.file_id, "line_number": f.line_number})
    return {"results": results}
    
@app.get("/api/repos/{repo_name}/stats")
def get_stats(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    return query_layer.model.analyses.metrics

@app.get("/api/repos/{repo_name}/summary")
def get_summary(repo_name: str):
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / repo_name
    
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

@app.post("/api/repos/{repo_name}/summary/generate")
def generate_summary(repo_name: str, background_tasks: BackgroundTasks):
    current_status = get_task_status(repo_name, "summary")
    if current_status == "processing":
        return {"status": "processing"}
    
    set_task_status(repo_name, "summary", "processing")
    
    def background_generate_summary():
        try:
            repos_dir = BASE_DIR / "data/repos"
            target_dir = repos_dir / repo_name
            query_layer = get_or_build_model(repo_name)
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
            set_task_status(repo_name, "summary", "completed")
        except Exception as e:
            import traceback
            logger.error(f"Summary generation failed: \\n{traceback.format_exc()}")
            set_task_status(repo_name, "summary", "failed")
            
    background_tasks.add_task(background_generate_summary)
    return {"status": "processing"}

@app.get("/api/repos/{repo_name}/semantic-status")
def semantic_status_repo(repo_name: str):
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / repo_name
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    state_file = target_dir / "semantic_index_state.json"
    return {"has_index": state_file.exists()}

@app.post("/api/repos/{repo_name}/semantic-index")
def semantic_index_repo(repo_name: str, background_tasks: BackgroundTasks):
    current_status = get_task_status(repo_name, "semantic_index")
    if current_status == "processing":
        return {"status": "processing"}
        
    set_task_status(repo_name, "semantic_index", "processing")
    
    def background_semantic_index():
        try:
            query_layer = get_or_build_model(repo_name)
            target_dir = BASE_DIR / "data/repos" / repo_name
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
                set_task_status(repo_name, "semantic_index", "completed")
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
            import ast
            for rel_str in files_to_process:
                pf = target_dir / rel_str
                try:
                    with open(pf, "r", encoding="utf-8") as f:
                        source = f.read()
                    tree = ast.parse(source)
                    for node in tree.body:
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                            segment = ast.get_source_segment(source, node)
                            if not segment: continue
                            element_type = "class" if isinstance(node, ast.ClassDef) else "function"
                            documents.append(segment)
                            metadatas.append({
                                "file_path": rel_str,
                                "type": element_type,
                                "name": node.name
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
            set_task_status(repo_name, "semantic_index", "completed")
        except Exception as e:
            logger.error(f"Semantic index failed: {e}")
            set_task_status(repo_name, "semantic_index", "failed")

    background_tasks.add_task(background_semantic_index)
    return {"status": "processing"}

@app.get("/api/repos/{repo_name}/semantic-search")
def semantic_search_repo(repo_name: str, q: str):
    if not q or len(q.strip()) == 0:
        return {"results": []}
        
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / repo_name
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

@app.get("/api/repos/{repo_name}/graph/search")
def graph_search(repo_name: str, q: str):
    query_layer = get_or_build_model(repo_name)
    service = GraphQueryService(query_layer.model)
    return {"results": service.search(q)}

@app.post("/api/repos/{repo_name}/graph/query")
def graph_query(repo_name: str, req: GraphQueryRequest):
    query_layer = get_or_build_model(repo_name)
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

@app.get("/api/repos/{repo_name}/health/scores")
def get_health_scores(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    health = getattr(query_layer.model.analyses, "health", None)
    if not health:
        raise HTTPException(status_code=404, detail="Health scores not found")
    return _serialize_dataclass(health)

@app.get("/api/repos/{repo_name}/health/metrics")
def get_health_metrics(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    metrics = getattr(query_layer.model.analyses, "metrics", None)
    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")
    return _serialize_dataclass(metrics)

@app.get("/api/repos/{repo_name}/health/findings")
def get_health_findings(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    findings = getattr(query_layer.model.analyses, "findings", [])
    return {"findings": _serialize_dataclass(findings)}

@app.get("/api/repos/{repo_name}/health/layers")
def get_health_layers(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    architecture = getattr(query_layer.model.analyses, "architecture", {})
    layers = [{"module_id": k, "layer": _serialize_dataclass(v)} for k, v in architecture.items()]
    return {"layers": layers}

@app.get("/api/repos/{repo_name}/health/dependencies")
def get_health_dependencies(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    dep_graph = getattr(query_layer.model.analyses, "dependency_graph", None)
    if not dep_graph:
        return {"edges": []}
    
    edges = getattr(dep_graph, "edges", None) or []
    return {"edges": _serialize_dataclass(edges)}

@app.get("/api/repos/{repo_name}/health/cycles")
def get_health_cycles(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    cycles = getattr(query_layer.model.analyses, "cycles", None) or []
    return {"cycles": _serialize_dataclass(cycles)}

@app.get("/api/repos/{repo_name}/health/dead-code")
def get_health_dead_code(repo_name: str):
    query_layer = get_or_build_model(repo_name)
    findings = getattr(query_layer.model.analyses, "findings", None) or []
    dead_code = [f for f in findings if "Unused" in f.title or "Unreachable" in f.title]
    return {"findings": _serialize_dataclass(dead_code)}

@app.get("/api/repos/{repo_name}/health/smells")
def get_health_smells(repo_name: str):
    query_layer = get_or_build_model(repo_name)
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
@app.get("/api/repos/{repo_name}/trace")
def trace_feature(repo_name: str, q: str):
    if not q or len(q.strip()) == 0:
        return {"trace": None}
        
    # Stage 1: Semantic search
    repos_dir = BASE_DIR / "data/repos"
    target_dir = repos_dir / repo_name
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
                query_layer = get_or_build_model(repo_name)
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
    # Let's see how get_or_build_model is defined in main.py... oh it's query_layer = get_or_build_model(repo_name)
    try:
        query_layer = get_or_build_model(repo_name)
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

@app.post("/api/repos/{repo_name}/trace/explain")
def explain_trace(repo_name: str, req: ExplainTraceRequest):
    prompt = f"Explain the following implementation trace for the feature '{req.feature_query}'. The trace was deterministically generated from the repository's semantic, dependency, and call graphs. Do not add any new nodes or hallucinate execution paths. Explain what each component does in the context of the flow.\n\nTrace Data: {json.dumps(req.trace_data, indent=2)}"
    
    try:
        explanation = llm_service.generate_explanation(prompt)
        return {"explanation": explanation}
    except Exception as e:
        logger.error(f"Explanation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate explanation")
