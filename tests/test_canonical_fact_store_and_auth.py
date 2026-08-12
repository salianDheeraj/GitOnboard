import pytest
from sqlalchemy import inspect, create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.database import Base, get_db
from backend.main import app
from backend.models.user import User
from backend.models.repository import Repository
from backend.models.fact_store import SymbolRecord, RelationshipRecord, RouteRecord, CapabilityRecord
from backend.services.github_oauth import create_jwt

from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_fact_store_tables_registered_in_base(db):
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # Verify canonical Fact Store tables are created
    assert "symbols" in tables
    assert "relationships" in tables
    assert "routes" in tables
    assert "capabilities" in tables
    assert "capability_members" in tables
    assert "evidence" in tables
    assert "files" in tables

def test_intelligence_endpoints_require_auth_and_ownership(db):
    # Override get_db for TestClient
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    # 1. Create User 1 & User 2
    user1 = User(id=1, github_id="gh1", email="user1@example.com", username="user1")
    user2 = User(id=2, github_id="gh2", email="user2@example.com", username="user2")
    db.add(user1)
    db.add(user2)
    db.commit()

    # 2. Create Repository for User 1
    repo1 = Repository(id=10, url="https://github.com/user1/myrepo", user_id=user1.id)
    db.add(repo1)
    db.commit()

    # Seed a symbol for repo1
    sym = SymbolRecord(
        id="sym_123",
        file_id="10:app.py",
        name="test_func",
        qualified_name="app.test_func",
        symbol_type="function",
        line_start=1,
        line_end=5
    )
    db.add(sym)
    db.commit()

    # 3. Unauthenticated request -> 401
    resp = client.get("/api/repo/10/symbol/sym_123")
    assert resp.status_code == 401

    # 4. User 2 (unauthorized) request -> 404 (IDOR protection)
    token_user2 = create_jwt(user2)
    client.cookies.set("access_token", token_user2)
    resp = client.get("/api/repo/10/symbol/sym_123")
    assert resp.status_code == 404

    # 5. User 1 (owner) request -> 200 OK
    token_user1 = create_jwt(user1)
    client.cookies.set("access_token", token_user1)
    resp = client.get("/api/repo/10/symbol/sym_123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test_func"

    app.dependency_overrides.clear()


def test_fact_store_batching(db):
    from backend.intelligence.store.fact_store import FactStore
    from backend.models.fact_store import SymbolRecord

    store = FactStore(db)
    # Generate 550 test symbols across multiple batch boundaries (BATCH_SIZE = 500)
    symbols = [
        {
            "stable_id": f"sym_batch_{i}",
            "file_id": f"file_{i}",
            "name": f"func_{i}",
            "qualified_name": f"mod.func_{i}",
            "symbol_type": "function",
            "line_start": 1,
            "line_end": 10
        }
        for i in range(550)
    ]
    store.save_symbols(symbols)

    count = db.query(SymbolRecord).count()
    assert count == 550

    # Re-save updated batch to verify merge handling
    symbols[0]["name"] = "updated_func_0"
    store.save_symbols(symbols[:10])

    updated_sym = db.query(SymbolRecord).filter(SymbolRecord.id == "sym_batch_0").first()
    assert updated_sym.name == "updated_func_0"


def test_llm_service_failure_fallback():
    from backend.llm_service import LLMService, EvidenceBackedAIPipeline
    from unittest.mock import MagicMock

    # Point to invalid port to simulate connection failure
    svc = LLMService(base_url="http://127.0.0.1:99999")
    
    # 1. Summary fallback
    meta = {"repository": {"name": "TestRepo"}, "statistics": {"files": 42}}
    summary = svc.generate_summary(meta)
    assert "TestRepo — Repository Summary" in summary

    # 2. Explanation fallback
    exp = svc.generate_explanation("Explain this feature")
    assert "Generated explanation grounded in AST-bounded source code" in exp

    # 3. Pipeline fallback
    mock_db = MagicMock()
    mock_db.query.return_value.all.return_value = []
    pipeline = EvidenceBackedAIPipeline(mock_db, "repo1")
    resp = pipeline.process_user_query("What does symbol 070589889afe6051d846bc77b4e2607f do?")
    assert "explanation" in resp
    assert isinstance(resp["explanation"], str)

