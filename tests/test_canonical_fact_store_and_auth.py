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
