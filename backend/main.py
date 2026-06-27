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
