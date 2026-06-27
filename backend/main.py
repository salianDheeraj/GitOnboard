from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
import shutil
from pathlib import Path
import logging

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
        result = subprocess.run(
            ["git", "clone", repo_url, str(target_dir)],
            check=True,
            capture_output=True,
            text=True,
            env=env
        )
        logger.info(f"Successfully cloned {repo_name}")
        return {"message": "Repository imported successfully", "repo": repo_name}
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone repository: {e.stderr}")
        raise HTTPException(status_code=500, detail=f"Failed to clone repository: {e.stderr}")

@app.get("/api/repos")
def list_repos():
    repos_dir = Path("data/repos")
    if not repos_dir.exists():
        return {"repositories": []}
    
    repos = []
    for d in repos_dir.iterdir():
        if d.is_dir():
            repos.append(d.name)
    return {"repositories": repos}

@app.delete("/api/repos/{repo_name}")
def delete_repo(repo_name: str):
    repos_dir = Path("data/repos")
    target_dir = repos_dir / repo_name
    
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail="Repository not found")
        
    try:
        shutil.rmtree(target_dir)
        logger.info(f"Deleted repository {repo_name}")
        return {"message": "Repository deleted successfully"}
    except Exception as e:
        logger.error(f"Failed to delete repository {repo_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete repository")
