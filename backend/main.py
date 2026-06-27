from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

METADATA_FILE = Path("data/repos_metadata.json")

def load_metadata():
    if METADATA_FILE.exists():
        with open(METADATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_metadata(data):
    with open(METADATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

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
    repos_dir = Path("data/repos")
    repos_dir.mkdir(parents=True, exist_ok=True)
    
    target_dir = repos_dir / repo_name
    
    if target_dir.exists():
        logger.info(f"Repository {repo_name} already exists.")
        return {"message": f"Repository {repo_name} already imported.", "repo": repo_name}

    logger.info(f"Cloning repository {repo_url} into {target_dir}")
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    
    try:
        subprocess.run(
            ["git", "clone", repo_url, str(target_dir)],
            check=True,
            capture_output=True,
            text=True,
            env=env
        )
        logger.info(f"Successfully cloned {repo_name}")
        
        # Phase 1 constraint: Ignore directories during processing (by removing them)
        ignored_dirs = [".git", "node_modules", "venv", "build", "dist", "__pycache__"]
        for d in ignored_dirs:
            p = target_dir / d
            if p.exists() and p.is_dir():
                shutil.rmtree(p)
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
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone repository: {e.stderr}")
        raise HTTPException(status_code=500, detail=f"Failed to clone repository: {e.stderr}")

@app.get("/api/repos")
def list_repos():
    metadata = load_metadata()
    return {"repositories": list(metadata.values())}

@app.delete("/api/repos/{repo_name}")
def delete_repo(repo_name: str):
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    try:
        shutil.rmtree(target_dir)
        metadata = load_metadata()
        if repo_name in metadata:
            del metadata[repo_name]
            save_metadata(metadata)
            
        logger.info(f"Deleted repository {repo_name}")
        return {"message": "Repository deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete repository {repo_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete repository")

@app.get("/api/repos/{repo_name}/scan")
def scan_repo(repo_name: str):
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    ignored_dirs = {".git", "node_modules", "venv", "build", "dist", "__pycache__"}
    
    total_files = 0
    total_python_files = 0
    total_directories = 0
    
    files_metadata = []
    
    # We will build a hierarchy. 
    # Nodes are dicts: {"name": str, "type": "file"|"directory", "children": []}
    def build_tree(current_path: Path):
        nonlocal total_files, total_python_files, total_directories
        
        node = {
            "name": current_path.name,
            "type": "directory",
            "children": []
        }
        
        try:
            # Sort for deterministic output: directories first, then files
            entries = sorted(list(current_path.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
        except PermissionError:
            return node
            
        for entry in entries:
            if entry.is_dir():
                if entry.name in ignored_dirs:
                    continue
                total_directories += 1
                node["children"].append(build_tree(entry))
            elif entry.is_file():
                total_files += 1
                ext = entry.suffix.lower()
                if ext == ".py":
                    total_python_files += 1
                    lang = "Python"
                elif ext in [".js", ".jsx"]:
                    lang = "JavaScript"
                elif ext in [".ts", ".tsx"]:
                    lang = "TypeScript"
                elif ext in [".html", ".htm"]:
                    lang = "HTML"
                elif ext == ".css":
                    lang = "CSS"
                elif ext == ".json":
                    lang = "JSON"
                elif ext == ".md":
                    lang = "Markdown"
                else:
                    lang = "Unknown"
                    
                try:
                    stat = entry.stat()
                    files_metadata.append({
                        "path": str(entry.relative_to(target_dir)).replace("\\", "/"),
                        "extension": ext,
                        "language": lang,
                        "size": stat.st_size,
                        "modified_time": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                    })
                except Exception:
                    pass
                
                node["children"].append({
                    "name": entry.name,
                    "type": "file",
                    "path": str(entry.relative_to(target_dir)).replace("\\", "/")
                })
        return node

    # For the root, we don't count it as a directory in our stats
    hierarchy = build_tree(target_dir)
    
    return {
        "overview": {
            "total_files": total_files,
            "total_python_files": total_python_files,
            "total_directories": total_directories
        },
        "hierarchy": hierarchy,
        "files": files_metadata
    }

@app.get("/api/repos/{repo_name}/parse")
def parse_repo_file(repo_name: str, file_path: str):
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    full_path = target_dir / file_path
    
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
        
    if not str(full_path).endswith(".py"):
        raise HTTPException(status_code=400, detail="Only Python files can be parsed")
        
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            source = f.read()
            
        tree = ast.parse(source)
        
        result = {
            "imports": [],
            "functions": [],
            "classes": [],
            "docstring": ast.get_docstring(tree)
        }
        
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    result["imports"].append(f"{module}.{alias.name}")
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                result["functions"].append({
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "line_number": getattr(node, "lineno", None),
                    "parameters": [arg.arg for arg in getattr(node, "args", getattr(node, "args", None)).args] if hasattr(node, "args") else []
                })
            elif isinstance(node, ast.ClassDef):
                class_data = {
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "methods": []
                }
                for class_node in node.body:
                    if isinstance(class_node, ast.FunctionDef) or isinstance(class_node, ast.AsyncFunctionDef):
                        class_data["methods"].append({
                            "name": class_node.name,
                            "docstring": ast.get_docstring(class_node)
                        })
                result["classes"].append(class_data)
                
        return result
    except Exception as e:
        logger.error(f"Failed to parse file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse file: {e}")

@app.get("/api/repos/{repo_name}/dependencies")
def get_dependencies(repo_name: str):
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    ignored_dirs = {".git", "node_modules", "venv", "build", "dist", "__pycache__"}
    
    python_files = []
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if file.endswith(".py"):
                python_files.append(Path(root) / file)
                
    module_map = {}
    file_nodes = []
    
    for pf in python_files:
        rel_path = pf.relative_to(target_dir)
        rel_str = str(rel_path).replace("\\", "/")
        file_nodes.append(rel_str)
        
        parts = list(rel_path.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]
            
        if parts:
            module_name = ".".join(parts)
            module_map[module_name] = rel_str
            
    edges = set()
    
    for pf in python_files:
        rel_str = str(pf.relative_to(target_dir)).replace("\\", "/")
        
        try:
            with open(pf, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in module_map:
                            edges.add((rel_str, module_map[alias.name]))
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    
                    if node.level > 0:
                        parts = list(pf.relative_to(target_dir).parts)
                        current_mod_parts = parts[:-1]
                        
                        parent_mod_parts = current_mod_parts[:-(node.level - 1)] if node.level > 1 else current_mod_parts
                        resolved_module = ".".join(parent_mod_parts + ([module] if module else []))
                        
                        if resolved_module in module_map:
                            edges.add((rel_str, module_map[resolved_module]))
                        
                        for alias in node.names:
                            potential_module = f"{resolved_module}.{alias.name}" if resolved_module else alias.name
                            if potential_module in module_map:
                                edges.add((rel_str, module_map[potential_module]))
                    else:
                        if module in module_map:
                            edges.add((rel_str, module_map[module]))
                        for alias in node.names:
                            potential_module = f"{module}.{alias.name}" if module else alias.name
                            if potential_module in module_map:
                                edges.add((rel_str, module_map[potential_module]))
                            
        except Exception:
            pass
            
    nodes = [{"id": f, "label": Path(f).name, "full_path": f} for f in file_nodes]
    formatted_edges = [{"id": f"e-{s}-{t}", "source": s, "target": t} for s, t in edges]
    
    return {"nodes": nodes, "edges": formatted_edges}

@app.post("/api/repos/{repo_name}/index")
def index_repo(repo_name: str):
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    index_file = target_dir / "metadata_index.json"
    ignored_dirs = {".git", "node_modules", "venv", "build", "dist", "__pycache__"}
    
    indexed_files = []
    
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if file.endswith(".py"):
                pf = Path(root) / file
                rel_str = str(pf.relative_to(target_dir)).replace("\\", "/")
                
                try:
                    with open(pf, "r", encoding="utf-8") as f:
                        source = f.read()
                    
                    tree = ast.parse(source)
                    
                    imports = []
                    functions = []
                    classes = []
                    file_docstring = ast.get_docstring(tree) or ""
                    
                    for node in tree.body:
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.append(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            module = node.module or ""
                            for alias in node.names:
                                imports.append(f"{module}.{alias.name}" if module else alias.name)
                        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                            functions.append({
                                "name": node.name,
                                "docstring": ast.get_docstring(node) or ""
                            })
                        elif isinstance(node, ast.ClassDef):
                            class_data = {
                                "name": node.name,
                                "docstring": ast.get_docstring(node) or "",
                                "methods": []
                            }
                            for class_node in node.body:
                                if isinstance(class_node, ast.FunctionDef) or isinstance(class_node, ast.AsyncFunctionDef):
                                    class_data["methods"].append({
                                        "name": class_node.name,
                                        "docstring": ast.get_docstring(class_node) or ""
                                    })
                            classes.append(class_data)
                            
                    indexed_files.append({
                        "file_path": rel_str,
                        "file_name": pf.name,
                        "docstring": file_docstring,
                        "imports": imports,
                        "functions": functions,
                        "classes": classes
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to parse {rel_str} during indexing: {e}")
                    pass
                    
    try:
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(indexed_files, f, indent=2)
        return {"message": "Indexing complete", "indexed_files_count": len(indexed_files)}
    except Exception as e:
        logger.error(f"Failed to save index: {e}")
        raise HTTPException(status_code=500, detail="Failed to save index")

@app.get("/api/repos/{repo_name}/search")
def search_repo(repo_name: str, q: str):
    if not q or len(q.strip()) == 0:
        return {"results": []}
        
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    index_file = target_dir / "metadata_index.json"
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    if not index_file.exists():
        # Auto-trigger indexing if it doesn't exist
        index_repo(repo_name)
        
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            indexed_files = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to load index")
        
    query = q.lower()
    results = []
    
    for item in indexed_files:
        is_match = False
        match_reasons = []
        
        # Check file name
        if query in item["file_name"].lower():
            is_match = True
            match_reasons.append(f"File name matches: {item['file_name']}")
            
        # Check file docstring
        if query in item["docstring"].lower():
            is_match = True
            match_reasons.append("File docstring matches")
            
        # Check imports
        for imp in item["imports"]:
            if query in imp.lower():
                is_match = True
                match_reasons.append(f"Import matches: {imp}")
                
        # Check functions
        for func in item["functions"]:
            if query in func["name"].lower():
                is_match = True
                match_reasons.append(f"Function matches: {func['name']}")
            elif query in func["docstring"].lower():
                is_match = True
                match_reasons.append(f"Docstring in function '{func['name']}' matches")
                
        # Check classes
        for cls in item["classes"]:
            if query in cls["name"].lower():
                is_match = True
                match_reasons.append(f"Class matches: {cls['name']}")
            elif query in cls["docstring"].lower():
                is_match = True
                match_reasons.append(f"Docstring in class '{cls['name']}' matches")
            else:
                for method in cls["methods"]:
                    if query in method["name"].lower():
                        is_match = True
                        match_reasons.append(f"Method matches: {method['name']} in class {cls['name']}")
                    elif query in method["docstring"].lower():
                        is_match = True
                        match_reasons.append(f"Docstring in method '{method['name']}' matches")
                        
        if is_match:
            results.append({
                "file_path": item["file_path"],
                "match_reasons": list(set(match_reasons))[:3] # Limit to top 3 reasons
            })
            
    return {"results": results}

@app.get("/api/repos/{repo_name}/semantic-status")
def semantic_status_repo(repo_name: str):
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    state_file = target_dir / "semantic_index_state.json"
    return {"has_index": state_file.exists()}

@app.post("/api/repos/{repo_name}/semantic-index")
def semantic_index_repo(repo_name: str):
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    chroma_dir = target_dir / "chroma"
    chroma_dir.mkdir(parents=True, exist_ok=True)
    
    state_file = target_dir / "semantic_index_state.json"
    state = {}
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
        except Exception:
            state = {}
            
    from chromadb.api.shared_system_client import SharedSystemClient
    SharedSystemClient.clear_system_cache()
    client = chromadb.PersistentClient(path=str(chroma_dir.absolute()))
    collection = client.get_or_create_collection(name="semantic_index")
    
    ignored_dirs = {".git", "node_modules", "venv", "build", "dist", "__pycache__"}
    
    current_files = {}
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if file.endswith(".py") and not file.startswith("."):
                pf = Path(root) / file
                rel_str = str(pf.relative_to(target_dir)).replace("\\", "/")
                try:
                    mtime = pf.stat().st_mtime
                    current_files[rel_str] = mtime
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
        return {"message": "Semantic index up to date", "status": status, "processed": 0, "deleted": 0}
        
    # Delete old chunks for modified and deleted files
    if files_to_delete_chunks:
        for f in files_to_delete_chunks:
            try:
                collection.delete(where={"file_path": f})
            except Exception as e:
                logger.warning(f"Failed to delete old chunks for {f}: {e}")
                pass
                
    documents = []
    metadatas = []
    ids = []
    
    import uuid
    
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
        except Exception as e:
            logger.warning(f"Failed to parse {rel_str} for semantic indexing: {e}")
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
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save state file: {e}")
        
    return {
        "message": "Semantic indexing complete",
        "status": status,
        "processed": len(files_to_process),
        "deleted": len(deleted_files)
    }

@app.get("/api/repos/{repo_name}/semantic-search")
def semantic_search_repo(repo_name: str, q: str):
    if not q or len(q.strip()) == 0:
        return {"results": []}
        
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    chroma_dir = target_dir / "chroma"
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    if not chroma_dir.exists():
        # Auto-trigger indexing if the database hasn't been created yet
        semantic_index_repo(repo_name)
        
    try:
        from chromadb.api.shared_system_client import SharedSystemClient
        SharedSystemClient.clear_system_cache()
        client = chromadb.PersistentClient(path=str(chroma_dir.absolute()))
        collection = client.get_collection(name="semantic_index")
    except Exception as e:
        logger.error(f"Failed to load Chroma collection: {e}")
        raise HTTPException(status_code=500, detail="Semantic index not found or corrupted")
        
    try:
        # Query the semantic index using natural language
        query_results = collection.query(
            query_texts=[q],
            n_results=10
        )
        
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
        logger.error(f"Semantic search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

def _gather_repo_metadata(repo_name: str, target_dir: Path) -> dict:
    ignored_dirs = {".git", "node_modules", "venv", "build", "dist", "__pycache__"}
    
    ext_to_lang = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", 
        ".html": "HTML", ".css": "CSS", ".java": "Java",
        ".cpp": "C++", ".c": "C", ".go": "Go", ".rs": "Rust"
    }
    
    languages = set()
    modules = set()
    entry_points = []
    file_sizes = []
    
    # folder structure representation
    structure = {}
    
    for root, dirs, files in os.walk(target_dir):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        
        rel_root = str(Path(root).relative_to(target_dir)).replace("\\", "/")
        if rel_root == ".":
            current_level = structure
        else:
            parts = rel_root.split("/")
            current_level = structure
            for p in parts:
                if p not in current_level:
                    current_level[p] = {}
                current_level = current_level[p]
                
        for file in files:
            if not file.startswith("."):
                current_level[file] = "file"
                
                ext = Path(file).suffix
                if ext in ext_to_lang:
                    languages.add(ext_to_lang[ext])
                
                # Check for modules (top level directories containing code)
                if rel_root != "." and rel_root.split("/")[0] not in ignored_dirs and ext == ".py":
                    modules.add(rel_root.split("/")[0])
                    
                pf = Path(root) / file
                try:
                    size = pf.stat().st_size
                    rel_path = str(pf.relative_to(target_dir)).replace("\\", "/")
                    file_sizes.append((rel_path, size))
                    
                    # Detect entry points
                    if ext == ".py":
                        if file in ["main.py", "app.py", "run.py", "__main__.py"]:
                            entry_points.append(rel_path)
                        elif size < 100000: # only scan small files to save time
                            with open(pf, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                                if "__name__" in content and ("'__main__'" in content or '"__main__"' in content):
                                    if rel_path not in entry_points:
                                        entry_points.append(rel_path)
                except Exception:
                    pass

    # Sort file sizes and get top 5
    file_sizes.sort(key=lambda x: x[1], reverse=True)
    largest_files = [f"{f[0]} ({f[1]} bytes)" for f in file_sizes[:5]]
    
    # Dependencies
    dependencies = []
    deps_file = Path("data/repos") / repo_name / "dependency_graph.json"
    if deps_file.exists():
        try:
            with open(deps_file, "r") as f:
                deps_data = json.load(f)
                nodes = deps_data.get("nodes", [])
                dependencies = [n["id"] for n in nodes if n.get("type") == "third-party"]
        except Exception:
            pass

    return {
        "repository_name": repo_name,
        "languages": list(languages),
        "modules": list(modules),
        "dependencies": dependencies[:20], # limit to avoid huge prompts
        "entry_points": entry_points,
        "largest_files": largest_files,
        "folder_structure": structure
    }

@app.post("/api/repos/{repo_name}/summary/generate")
def generate_summary(repo_name: str):
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    try:
        metadata = _gather_repo_metadata(repo_name, target_dir)
        summary_md = llm_service.generate_summary(metadata)
        
        summary_file = target_dir / "summary.md"
        with open(summary_file, "w", encoding="utf-8") as f:
            f.write(summary_md)
            
        return {"summary": summary_md, "status": "generated"}
    except Exception as e:
        import traceback
        logger.error(f"Summary generation failed:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/repos/{repo_name}/summary")
def get_summary(repo_name: str):
    repos_dir = Path("data/repos")
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
        # If semantic index state is newer than the summary, it's outdated
        if state_file.exists():
            summary_mtime = summary_file.stat().st_mtime
            state_mtime = state_file.stat().st_mtime
            if state_mtime > summary_mtime:
                outdated = True
                
        return {"summary": summary_md, "outdated": outdated}
    except Exception as e:
        logger.error(f"Failed to read summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to read summary")

