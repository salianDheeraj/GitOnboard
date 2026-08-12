import pytest
import ast
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.fact_store import Base, RouteRecord, SymbolRecord, RelationshipRecord, CapabilityRecord
from backend.intelligence.rim.identity import generate_stable_id, generate_entity_id
from backend.intelligence.rim.enums import EntityType
from backend.intelligence.engine.analyzers.symbol import SymbolAnalyzer
from backend.intelligence.engine.analyzers.route import RouteAnalyzer
from backend.intelligence.engine.analyzers.callgraph import CallGraphAnalyzer
from backend.intelligence.engine.parser.providers.base import ParsedFile
from backend.intelligence.store.fact_store import FactStore
from backend.intelligence.capabilities.rule_engine import DeterministicCapabilityEngine
from backend.intelligence.query_layer import RepositoryQueryEngine

engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_stable_id_formula_consistency():
    repo_id = "test_repo"
    file_path = "app/auth.py"
    qname = "app.auth.login"
    
    st_id1 = generate_stable_id(repo_id, file_path, qname, "")
    st_id2 = generate_entity_id(EntityType.FUNCTION, file_path, qname, repo_id=repo_id)
    
    assert len(st_id1) == 32
    assert st_id1 == st_id2

def test_analyzer_identity_alignment(db):
    repo_id = "repo1"
    file_path = "app/auth.py"
    
    source_code = """
def verify_password(plain, hashed):
    return True

@app.post("/login")
def login_user():
    return verify_password("secret", "hash")
"""
    parsed_ast = ast.parse(source_code)
    parsed_file = ParsedFile(
        file_path=file_path,
        language="Python",
        ast=parsed_ast,
        source=source_code
    )
    asts = {file_path: parsed_file}

    # 1. Extract symbols, routes, relationships
    sym_analyzer = SymbolAnalyzer(repo_id, file_path)
    route_analyzer = RouteAnalyzer(repo_id, file_path)
    call_analyzer = CallGraphAnalyzer(repo_id, file_path)

    symbols = sym_analyzer.extract_symbols(asts)
    routes = route_analyzer.extract_routes(asts, symbols)
    relationships = call_analyzer.extract_relationships(asts, symbols)

    assert len(symbols) >= 2
    assert len(routes) == 1
    assert len(relationships) >= 1

    # Save to FactStore DB
    fact_store = FactStore(db)
    fact_store.save_symbols(symbols)
    fact_store.save_routes(routes)
    fact_store.save_relationships(relationships)

    # Verify ID matching between Route, Symbol, and Relationship
    db_route = db.query(RouteRecord).first()
    login_symbol = db.query(SymbolRecord).filter(SymbolRecord.name == "login_user").first()
    verify_symbol = db.query(SymbolRecord).filter(SymbolRecord.name == "verify_password").first()
    rel = db.query(RelationshipRecord).filter(RelationshipRecord.to_symbol_id == verify_symbol.id).first()

    assert db_route is not None
    assert login_symbol is not None
    assert verify_symbol is not None
    assert rel is not None

    # Crucial assertion: Route handler_symbol_id MUST match SymbolRecord.id
    assert db_route.handler_symbol_id == login_symbol.id

    # Crucial assertion: Relationship from_symbol_id and to_symbol_id MUST match SymbolRecord.ids
    assert rel.from_symbol_id == login_symbol.id
    assert rel.to_symbol_id == verify_symbol.id

    # Test RepositoryQueryEngine with these stable IDs
    query_engine = RepositoryQueryEngine(db, repo_id)

    # findCallers of verify_password should return login_user
    callers = query_engine.findCallers(verify_symbol.id)
    assert len(callers) == 1
    assert callers[0]["name"] == "login_user"

    # findCallees of login_user should include verify_password
    callees = query_engine.findCallees(login_symbol.id)
    callee_names = [c["name"] for c in callees if c and "name" in c]
    assert "verify_password" in callee_names

    # traceExecution for the route should trace login_user and verify_password
    trace = query_engine.traceExecution(db_route.id)
    assert trace["path"] == "/login"
    exec_names = [step["name"] for step in trace["execution_path"] if "name" in step]
    assert "login_user" in exec_names
    assert "verify_password" in exec_names

    # Test CapabilityEngine rule for Authentication
    cap_engine = DeterministicCapabilityEngine(db, repo_id)
    cap_engine.detect_authentication()

    auth_cap = db.query(CapabilityRecord).filter(CapabilityRecord.name == "Authentication").first()
    assert auth_cap is not None
    assert auth_cap.status == "CONFIRMED"
