import pytest
import os
from pathlib import Path

from backend.intelligence.engine.orchestration.pipeline import AnalysisEngine
from backend.intelligence.engine.analyzers import get_default_registry

@pytest.fixture
def mock_repo(tmp_path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    
    (repo_dir / "package.json").write_text('{"name": "test_app", "dependencies": {"express": "4.17.1"}}')
    
    src = repo_dir / "src"
    src.mkdir()
    
    (src / "models.py").write_text('''
class User:
    __tablename__ = "users"
''')
    
    (src / "service.py").write_text('''
from .models import User

class UserService:
    def get_user(self, id):
        pass
''')

    (src / "routes.py").write_text('''
from fastapi import APIRouter
from .service import UserService

router = APIRouter()
svc = UserService()

@router.get("/users/{id}")
def get_user(id: int):
    return svc.get_user(id)
''')
    
    (src / "test_service.py").write_text('''
def test_get_user():
    pass
''')
    
    return str(repo_dir)


def test_analysis_engine(mock_repo):
    engine = AnalysisEngine(mock_repo, get_default_registry())
    model = engine.run("test_repo")
    
    assert model.metadata.name == "test_repo"
    
    # Check that config was parsed
    entities = list(model.entities.values())
    rels = list(model.relationships.values())
    
    assert any(e.type == "PACKAGE" and e.name == "test_app" for e in entities)
    assert any(e.type == "DEPENDENCY" and e.name == "express" for e in entities)
    
    # Check that python files were parsed
    assert any(e.type == "CLASS" and e.name == "UserService" for e in entities)
    assert any(e.type == "TABLE" and e.name == "users" for e in entities)
    assert any(e.type == "ROUTE" for e in entities)
    assert any(e.type == "TEST_CASE" and e.name == "test_get_user" for e in entities)
    
    # Check relationships
    assert any(r.type == "DECLARES" for r in rels)
    assert any(r.type == "IMPORTS" for r in rels)
    assert any(r.type == "CALLS" for r in rels)
    assert any(r.type == "EXPOSES" for r in rels)
    assert any(r.type == "USES" for r in rels) # from DatabaseAnalyzer
