from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.repository import Repository
from backend.dependencies.auth import get_current_user
from backend.intelligence.query_layer import RepositoryQueryEngine
from backend.intelligence.incremental import IncrementalUpdateEngine
from backend.intelligence.doc_generator import DocumentationGenerator

router = APIRouter(prefix="/api/repo/{repo_id}", tags=["intelligence"])

# --- Helper for Ownership Verification ---
def verify_repo_ownership(repo_id: str, db: Session, current_user: User) -> Repository:
    if repo_id.isdigit():
        repo = db.query(Repository).filter(
            Repository.id == int(repo_id),
            Repository.user_id == current_user.id
        ).first()
        if repo:
            return repo

    repos = db.query(Repository).filter(Repository.user_id == current_user.id).all()
    for r in repos:
        if (
            r.url.rstrip("/").endswith(f"/{repo_id}")
            or r.url.rstrip("/").endswith(f"/{repo_id}.git")
            or str(r.github_repo_id) == str(repo_id)
            or str(r.id) == str(repo_id)
        ):
            return r

    raise HTTPException(status_code=404, detail="Repository not found")

# --- Pydantic Schemas ---
class IncrementalPayload(BaseModel):
    changed_files: list[str]
    new_facts: list[dict] = []

# --- Query Engine Endpoints ---
@router.get("/symbol/{symbol_id}")
def get_symbol_definition(
    repo_id: str,
    symbol_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_repo_ownership(repo_id, db, current_user)
    engine = RepositoryQueryEngine(db, repo_id)
    result = engine.findDefinition(symbol_id)
    if not result:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return result

@router.get("/callers/{symbol_id}")
def get_symbol_callers(
    repo_id: str,
    symbol_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_repo_ownership(repo_id, db, current_user)
    engine = RepositoryQueryEngine(db, repo_id)
    return engine.findCallers(symbol_id)

@router.get("/callees/{symbol_id}")
def get_symbol_callees(
    repo_id: str,
    symbol_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_repo_ownership(repo_id, db, current_user)
    engine = RepositoryQueryEngine(db, repo_id)
    return engine.findCallees(symbol_id)

@router.get("/dependencies/{symbol_id}")
def get_symbol_dependencies(
    repo_id: str,
    symbol_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_repo_ownership(repo_id, db, current_user)
    engine = RepositoryQueryEngine(db, repo_id)
    return engine.findDependencies(symbol_id)

@router.get("/trace/{route_id}")
def trace_route_execution(
    repo_id: str,
    route_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_repo_ownership(repo_id, db, current_user)
    engine = RepositoryQueryEngine(db, repo_id)
    return engine.traceExecution(route_id)

@router.get("/impact/{symbol_id}")
def get_impact_analysis(
    repo_id: str,
    symbol_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_repo_ownership(repo_id, db, current_user)
    engine = RepositoryQueryEngine(db, repo_id)
    return engine.impactAnalysis(symbol_id)

# --- Incremental Update Endpoint ---
@router.post("/incremental")
def handle_incremental_update(
    repo_id: str, 
    payload: IncrementalPayload, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_repo_ownership(repo_id, db, current_user)
    engine = IncrementalUpdateEngine(db, repo_id)
    engine.process_file_changes(payload.changed_files, payload.new_facts)
    return {
        "status": "success", 
        "updated_files": payload.changed_files
    }

# --- Documentation Generator Endpoints ---
@router.get("/docs/mermaid")
def get_mermaid_diagram(
    repo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_repo_ownership(repo_id, db, current_user)
    doc_gen = DocumentationGenerator(db, repo_id)
    return {"mermaid_code": doc_gen.generate_mermaid_flowchart()}

@router.get("/docs/summary")
def get_architecture_summary(
    repo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_repo_ownership(repo_id, db, current_user)
    doc_gen = DocumentationGenerator(db, repo_id)
    return {"markdown": doc_gen.generate_readme_summary()}