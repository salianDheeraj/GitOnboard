from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from backend.models.fact_store import (
    SymbolRecord, RelationshipRecord, RouteRecord, 
    CapabilityRecord, CapabilityMemberRecord
)
from backend.intelligence.rim.enums import EntityType
from backend.intelligence.rim.entity import Entity
from backend.intelligence.rim.repository import RepositoryModel

class QueryLayer:
    """
    In-memory Repository Intelligence Model Query Layer.
    """
    def __init__(self, model: RepositoryModel):
        self.model = model
        self._build_indexes()

    def _build_indexes(self):
        self._func_name_idx: Dict[str, List[str]] = {}
        self._class_name_idx: Dict[str, List[str]] = {}
        self._file_to_classes_idx: Dict[str, List[str]] = {}
        self._module_to_functions_idx: Dict[str, List[str]] = {}

        for eid, entity in self.model.entities.items():
            if entity.type == EntityType.FUNCTION:
                self._func_name_idx.setdefault(entity.name, []).append(eid)
                module_id = entity.metadata.get("module_id", entity.location.repository_path)
                self._module_to_functions_idx.setdefault(module_id, []).append(eid)
            elif entity.type == EntityType.CLASS:
                self._class_name_idx.setdefault(entity.name, []).append(eid)
                file_id = entity.metadata.get("file_id", entity.location.repository_path)
                self._file_to_classes_idx.setdefault(file_id, []).append(eid)

    def find_function(self, name: str) -> List[Entity]:
        ids = self._func_name_idx.get(name, [])
        return [self.model.entities[eid] for eid in ids if eid in self.model.entities]

    def get_class(self, name: str) -> List[Entity]:
        ids = self._class_name_idx.get(name, [])
        return [self.model.entities[eid] for eid in ids if eid in self.model.entities]

    def get_file(self, file_id: str) -> Optional[Entity]:
        return self.model.entities.get(file_id)

    def get_dependencies(self, file_id: str) -> List[str]:
        return [r.target_id for r in self.model.relationships.values() if r.type == "DEPENDS_ON" and r.source_id == file_id]

    def get_calls(self, function_id: str) -> List[str]:
        return [r.target_id for r in self.model.relationships.values() if r.type == "CALLS" and r.source_id == function_id]

    def get_classes_in_file(self, file_id: str) -> List[Entity]:
        ids = self._file_to_classes_idx.get(file_id, [])
        return [self.model.entities[eid] for eid in ids if eid in self.model.entities]

    def get_functions_in_module(self, module_id: str) -> List[Entity]:
        ids = self._module_to_functions_idx.get(module_id, [])
        return [self.model.entities[eid] for eid in ids if eid in self.model.entities]

    def get_directories(self) -> List[Entity]:
        return [e for e in self.model.entities.values() if e.type == EntityType.DIRECTORY]

    def get_files(self) -> List[Entity]:
        return [e for e in self.model.entities.values() if e.type == EntityType.FILE]

    def search_entities(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        results = []
        for fn_name, fn_ids in self._func_name_idx.items():
            if query_lower in fn_name.lower():
                for eid in fn_ids:
                    fn = self.model.entities[eid]
                    results.append({"type": "function", "name": fn.name, "id": eid, "file": fn.location.repository_path})
        
        for cls_name, cls_ids in self._class_name_idx.items():
            if query_lower in cls_name.lower():
                for eid in cls_ids:
                    cls = self.model.entities[eid]
                    results.append({"type": "class", "name": cls.name, "id": eid, "file": cls.location.repository_path})
                    
        return results


class RepositoryQueryEngine:
    """
    Layer 7: Repository Query Engine
    Canonical API for retrieving ground truth intelligence directly from the Fact Store.
    """
    def __init__(self, db: Session, repo_id: str):
        self.db = db
        self.repo_id = repo_id

    # 1. Definition Lookup
    def findDefinition(self, symbol_id: str) -> Optional[Dict[str, Any]]:
        sym = self.db.query(SymbolRecord).filter(SymbolRecord.id == symbol_id).first()
        if not sym:
            return None
        return {
            "id": sym.id,
            "file_id": sym.file_id,
            "name": sym.name,
            "qualified_name": sym.qualified_name,
            "symbol_type": sym.symbol_type,
            "line_start": sym.line_start,
            "line_end": sym.line_end,
            "signature_hash": sym.signature_hash,
            "metadata": sym.symbol_metadata
        }

    # 2. Callers Lookup
    def findCallers(self, symbol_id: str) -> List[Dict[str, Any]]:
        relationships = self.db.query(RelationshipRecord).filter(
            RelationshipRecord.to_symbol_id == symbol_id,
            RelationshipRecord.rel_type == "CALLS"
        ).all()
        caller_ids = [r.from_symbol_id for r in relationships]
        callers = self.db.query(SymbolRecord).filter(SymbolRecord.id.in_(caller_ids)).all() if caller_ids else []
        return [{"id": c.id, "name": c.name, "qualified_name": c.qualified_name} for c in callers]

    # 3. Callees Lookup
    def findCallees(self, symbol_id: str) -> List[Dict[str, Any]]:
        relationships = self.db.query(RelationshipRecord).filter(
            RelationshipRecord.from_symbol_id == symbol_id,
            RelationshipRecord.rel_type == "CALLS"
        ).all()
        callee_ids = [r.to_symbol_id for r in relationships]
        callees = self.db.query(SymbolRecord).filter(SymbolRecord.id.in_(callee_ids)).all() if callee_ids else []
        return [{"id": c.id, "name": c.name, "qualified_name": c.qualified_name} for c in callees]

    # 4. Dependency Traversal
    def findDependencies(self, symbol_id: str) -> List[Dict[str, Any]]:
        relationships = self.db.query(RelationshipRecord).filter(
            RelationshipRecord.from_symbol_id == symbol_id,
            RelationshipRecord.rel_type.in_(["IMPORTS", "USES", "QUERIES"])
        ).all()
        dep_ids = [r.to_symbol_id for r in relationships]
        deps = self.db.query(SymbolRecord).filter(SymbolRecord.id.in_(dep_ids)).all() if dep_ids else []
        return [{"id": d.id, "name": d.name, "symbol_type": d.symbol_type} for d in deps]

    # 5. Route Tracing & Replay
    def traceExecution(self, route_id: str) -> Dict[str, Any]:
        route = self.db.query(RouteRecord).filter(RouteRecord.id == route_id).first()
        if not route:
            return {}

        path = []
        visited = set()

        def dfs(current_id: str):
            if current_id in visited:
                return
            visited.add(current_id)
            sym = self.findDefinition(current_id)
            if sym:
                path.append(sym)
                callees = self.findCallees(current_id)
                for callee in callees:
                    dfs(callee["id"])

        dfs(route.handler_symbol_id)

        return {
            "route_id": route.id,
            "http_method": route.method,
            "path": route.path,
            "execution_path": path
        }

    # 6. Impact Analysis
    def impactAnalysis(self, symbol_id: str) -> Dict[str, Any]:
        affected_symbols = []
        visited = {symbol_id}
        queue = [symbol_id]

        while queue:
            curr = queue.pop(0)
            callers = self.db.query(RelationshipRecord).filter(
                RelationshipRecord.to_symbol_id == curr,
                RelationshipRecord.rel_type.in_(["CALLS", "IMPORTS", "USES"])
            ).all()

            for rel in callers:
                if rel.from_symbol_id not in visited:
                    visited.add(rel.from_symbol_id)
                    queue.append(rel.from_symbol_id)
                    sym = self.findDefinition(rel.from_symbol_id)
                    if sym:
                        affected_symbols.append(sym)

        affected_symbol_ids = [s["id"] for s in affected_symbols]
        affected_routes = self.db.query(RouteRecord).filter(
            RouteRecord.handler_symbol_id.in_(affected_symbol_ids)
        ).all() if affected_symbol_ids else []

        return {
            "target_symbol_id": symbol_id,
            "total_affected_symbols": len(affected_symbols),
            "affected_symbols": affected_symbols,
            "affected_routes": [{"method": r.method, "path": r.path} for r in affected_routes]
        }