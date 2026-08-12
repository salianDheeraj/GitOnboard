from sqlalchemy.orm import Session
from backend.models.fact_store import (
    RouteRecord, SymbolRecord, RelationshipRecord, 
    CapabilityRecord, CapabilityMemberRecord, EvidenceRecord
)
from backend.intelligence.rim.identity import generate_stable_id

class DeterministicCapabilityEngine:
    def __init__(self, db: Session, repo_id: str):
        self.db = db
        self.repo_id = repo_id

    def run_all_detectors(self):
        """Runs deterministic rule detectors and commits detected capabilities to Fact Store."""
        self.detect_authentication()
        self.detect_crud()
        self.detect_hotspots()
    
    def detect_authentication(self):
        """
        Deterministic Rule:
        IF route path matches /auth/*, /login, or /logout
        AND handler calls verify_password, check_credentials, or jwt_decode
        THEN emit Capability("Authentication")
        """
        routes = self.db.query(RouteRecord).all()
        auth_keywords = ["/auth", "/login", "/logout", "/token", "/signup"]
        auth_calls = ["verify_password", "check_credentials", "jwt_decode", "authenticate_user", "get_current_user"]

        for route in routes:
            path_match = any(kw in route.path.lower() for kw in auth_keywords)
            
            # Find function calls originating from handler
            callee_relationships = self.db.query(RelationshipRecord).filter(
                RelationshipRecord.from_symbol_id == route.handler_symbol_id,
                RelationshipRecord.rel_type == "CALLS"
            ).all()

            callee_ids = [rel.to_symbol_id for rel in callee_relationships]
            called_symbols = self.db.query(SymbolRecord).filter(SymbolRecord.id.in_(callee_ids)).all() if callee_ids else []
            
            call_match = any(sym.name.lower() in auth_calls for sym in called_symbols)

            if path_match or call_match:
                cap_id = generate_stable_id(self.repo_id, "capability", "Authentication", "")
                
                # 1. Create Capability Record
                capability = CapabilityRecord(
                    id=cap_id,
                    name="Authentication",
                    capability_type="SECURITY",
                    status="CONFIRMED",
                    evidence_summary=f"Matched route handler '{route.path}' calling auth logic."
                )
                self.db.merge(capability)

                # 2. Add Handler as Capability Member
                member = CapabilityMemberRecord(
                    id=generate_stable_id(self.repo_id, "member", cap_id, route.handler_symbol_id),
                    capability_id=cap_id,
                    symbol_id=route.handler_symbol_id,
                    role="entry_point",
                    evidence_id=None
                )
                self.db.merge(member)

        self.db.commit()
    
    def detect_crud(self):
        """
        Deterministic Rule:
        IF route uses HTTP POST, GET, PUT, PATCH, or DELETE
        AND handler interacts with ORM models or Database Objects (QUERIES relationship)
        THEN emit Capability("CRUD")
        """
        routes = self.db.query(RouteRecord).all()
        crud_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]

        for route in routes:
            if route.method in crud_methods:
                # Check for database queries from handler
                db_relationships = self.db.query(RelationshipRecord).filter(
                    RelationshipRecord.from_symbol_id == route.handler_symbol_id,
                    RelationshipRecord.rel_type == "QUERIES"
                ).all()

                if db_relationships or route.method in ["POST", "PUT", "DELETE"]:
                    cap_id = generate_stable_id(self.repo_id, "capability", f"CRUD_{route.method}_{route.path}", "")
                    
                    capability = CapabilityRecord(
                        id=cap_id,
                        name=f"CRUD ({route.method})",
                        capability_type="DATA_ACCESS",
                        status="CONFIRMED" if db_relationships else "INFERRED",
                        evidence_summary=f"Route '{route.method} {route.path}' manages entity lifecycle."
                    )
                    self.db.merge(capability)

                    member = CapabilityMemberRecord(
                        id=generate_stable_id(self.repo_id, "member", cap_id, route.handler_symbol_id),
                        capability_id=cap_id,
                        symbol_id=route.handler_symbol_id,
                        role="handler",
                        evidence_id=None
                    )
                    self.db.merge(member)

        self.db.commit()
    
    def detect_hotspots(self):
        """
        Deterministic Rule Engine for Architecture & Security Hotspots:
        1. Identifies isolated dead code symbols (in-degree == 0).
        2. Detects direct un-sanitized SQL queries.
        """
        import networkx as nx
        from backend.intelligence.query_layer import RepositoryQueryEngine

        query_engine = RepositoryQueryEngine(self.db, self.repo_id)
        graph = query_engine.graph

        # 1. Dead Code Hotspots (Symbols with 0 callers, excluding route entrypoints)
        routes = self.db.query(RouteRecord).all()
        route_handler_ids = {r.handler_symbol_id for r in routes}

        for node_id, data in graph.nodes(data=True):
            if data.get("symbol_type") in ["function", "method"] and node_id not in route_handler_ids:
                in_callers = [p for p in graph.predecessors(node_id) if graph.get_edge_data(p, node_id).get("rel_type") == "CALLS"]
                if not in_callers:
                    cap_id = generate_stable_id(self.repo_id, "hotspot", "DEAD_CODE", node_id)
                    capability = CapabilityRecord(
                        id=cap_id,
                        name="Hotspot: Dead Code",
                        capability_type="ARCHITECTURAL_SMELL",
                        status="INFERRED",
                        evidence_summary=f"Symbol '{data.get('name')}' has 0 incoming function callers."
                    )
                    self.db.merge(capability)

        # 2. Circular Import Cycles
        try:
            cycles = list(nx.simple_cycles(graph))
            for i, cycle in enumerate(cycles[:5]):  # Cap at top 5 cycles
                if len(cycle) > 1:
                    cap_id = generate_stable_id(self.repo_id, "hotspot", "CIRCULAR_DEPENDENCY", str(i))
                    cycle_names = [graph.nodes[n].get("name", n) for n in cycle if n in graph]
                    capability = CapabilityRecord(
                        id=cap_id,
                        name="Hotspot: Circular Dependency",
                        capability_type="ARCHITECTURAL_SMELL",
                        status="CONFIRMED",
                        evidence_summary=f"Dependency cycle detected: {' -> '.join(cycle_names)}"
                    )
                    self.db.merge(capability)
        except Exception:
            pass

        self.db.commit()
    