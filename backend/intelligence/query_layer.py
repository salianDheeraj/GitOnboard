from typing import List, Dict, Optional, Any
import networkx as nx
from sqlalchemy.orm import Session
from backend.models.fact_store import (
    SymbolRecord, RelationshipRecord, RouteRecord, 
    CapabilityRecord, CapabilityMemberRecord
)

class RepositoryQueryEngine:
    """
    Layer 7: Repository Query Engine
    In-memory NetworkX graph projection over Fact Store tables for instant traversals.
    """
    def __init__(self, db: Session, repo_id: str):
        self.db = db
        self.repo_id = repo_id
        self.graph = nx.DiGraph()
        self._build_graph_projection()

    def _build_graph_projection(self):
        """Builds an in-memory directed graph of all symbols (nodes) and relationships (edges)."""
        # 1. Fetch symbols and add as nodes
        symbols = self.db.query(SymbolRecord).all()
        for sym in symbols:
            self.graph.add_node(
                sym.id,
                file_id=sym.file_id,
                name=sym.name,
                qualified_name=sym.qualified_name,
                symbol_type=sym.symbol_type,
                line_start=sym.line_start,
                line_end=sym.line_end,
                signature_hash=sym.signature_hash,
                metadata=sym.symbol_metadata
            )

        # 2. Fetch relationships and add as directed edges
        relationships = self.db.query(RelationshipRecord).all()
        for rel in relationships:
            self.graph.add_edge(
                rel.from_symbol_id,
                rel.to_symbol_id,
                rel_type=rel.rel_type,
                status=rel.status
            )

    # 1. Definition Lookup
    def findDefinition(self, symbol_id: str) -> Optional[Dict[str, Any]]:
        if symbol_id not in self.graph:
            return None
        node_data = self.graph.nodes[symbol_id]
        return {"id": symbol_id, **node_data}

    # 2. Callers Lookup (In-degree nodes with CALLS relationship)
    def findCallers(self, symbol_id: str) -> List[Dict[str, Any]]:
        if symbol_id not in self.graph:
            return []
        
        callers = []
        for predecessor in self.graph.predecessors(symbol_id):
            edge_data = self.graph.get_edge_data(predecessor, symbol_id)
            if edge_data.get("rel_type") == "CALLS":
                callers.append(self.findDefinition(predecessor))
        return callers

    # 3. Callees Lookup (Out-degree nodes with CALLS relationship)
    def findCallees(self, symbol_id: str) -> List[Dict[str, Any]]:
        if symbol_id not in self.graph:
            return []

        callees = []
        for successor in self.graph.successors(symbol_id):
            edge_data = self.graph.get_edge_data(symbol_id, successor)
            if edge_data.get("rel_type") == "CALLS":
                callees.append(self.findDefinition(successor))
        return callees

    # 4. Dependency Traversal
    def findDependencies(self, symbol_id: str) -> List[Dict[str, Any]]:
        if symbol_id not in self.graph:
            return []

        deps = []
        for successor in self.graph.successors(symbol_id):
            edge_data = self.graph.get_edge_data(symbol_id, successor)
            if edge_data.get("rel_type") in ["IMPORTS", "USES", "QUERIES"]:
                deps.append(self.findDefinition(successor))
        return deps

    # 5. Route Tracing & Replay via NetworkX DFS
    def traceExecution(self, route_id: str) -> Dict[str, Any]:
        route = self.db.query(RouteRecord).filter(RouteRecord.id == route_id).first()
        if not route or route.handler_symbol_id not in self.graph:
            return {}

        execution_path = []
        # DFS traversal starting from route handler
        visited_nodes = list(nx.dfs_preorder_nodes(self.graph, source=route.handler_symbol_id))
        for node_id in visited_nodes:
            def_data = self.findDefinition(node_id)
            if def_data:
                execution_path.append(def_data)

        return {
            "route_id": route.id,
            "http_method": route.method,
            "path": route.path,
            "execution_path": execution_path
        }

    # 6. Impact Analysis via Reverse Graph Traversal
    def impactAnalysis(self, symbol_id: str) -> Dict[str, Any]:
        """Calculates all downstream affected nodes using graph reachability on reverse edges."""
        if symbol_id not in self.graph:
            return {"target_symbol_id": symbol_id, "total_affected_symbols": 0, "affected_symbols": [], "affected_routes": []}

        # Create reversed graph to trace backwards from changed symbol
        reversed_graph = self.graph.reverse(copy=True)
        affected_node_ids = list(nx.descendants(reversed_graph, source=symbol_id))

        affected_symbols = [self.findDefinition(nid) for nid in affected_node_ids if nid in self.graph]

        # Check affected API routes
        affected_routes = self.db.query(RouteRecord).filter(
            RouteRecord.handler_symbol_id.in_(affected_node_ids)
        ).all() if affected_node_ids else []

        return {
            "target_symbol_id": symbol_id,
            "total_affected_symbols": len(affected_symbols),
            "affected_symbols": affected_symbols,
            "affected_routes": [{"method": r.method, "path": r.path} for r in affected_routes]
        }
# Backward compatibility alias
QueryLayer = RepositoryQueryEngine