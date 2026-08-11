import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models.fact_store import Base, RouteRecord, SymbolRecord, CapabilityRecord
from backend.intelligence.capabilities.rule_engine import DeterministicCapabilityEngine
from backend.intelligence.query_layer import RepositoryQueryEngine

# Setup in-memory SQLite DB for testing
engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_deterministic_authentication_capability(db):
    # 1. Seed Mock Fact Store
    handler_symbol = SymbolRecord(
        id="sym_auth_handler",
        file_id="repo1:auth.py",
        name="login_user",
        qualified_name="auth.py:login_user",
        symbol_type="function",
        line_start=10,
        line_end=25
    )
    route = RouteRecord(
        id="route_login",
        symbol_id="sym_route_login",
        method="POST",
        path="/login",
        handler_symbol_id="sym_auth_handler"
    )
    db.add(handler_symbol)
    db.add(route)
    db.commit()

    # 2. Run Capability Detection Rule Engine
    cap_engine = DeterministicCapabilityEngine(db, "repo1")
    cap_engine.detect_authentication()

    # 3. Assert Ground Truth Compliance
    cap = db.query(CapabilityRecord).filter(CapabilityRecord.name == "Authentication").first()
    assert cap is not None
    assert cap.status == "CONFIRMED"

def test_query_engine_trace_execution(db):
    # Seed mock symbols and routes
    handler = SymbolRecord(
        id="sym_handler",
        file_id="repo1:main.py",
        name="get_items",
        qualified_name="main.py:get_items",
        symbol_type="function",
        line_start=1,
        line_end=10
    )
    route = RouteRecord(
        id="route_items",
        symbol_id="sym_route_items",
        method="GET",
        path="/items",
        handler_symbol_id="sym_handler"
    )
    db.add(handler)
    db.add(route)
    db.commit()

    query_engine = RepositoryQueryEngine(db, "repo1")
    trace = query_engine.traceExecution("route_items")

    assert trace["http_method"] == "GET"
    assert trace["path"] == "/items"
    assert len(trace["execution_path"]) == 1
    assert trace["execution_path"][0]["name"] == "get_items"