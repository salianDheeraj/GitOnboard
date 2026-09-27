"""
Fact Store Graph Traverser: Executes analysis-scoped deterministic relationship traversal
on FactRelationship, FactRoute, and FactDatabaseObject tables.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.models.fact_store import (
    FactFile,
    FactSymbol,
    FactRelationship,
    FactRoute,
    FactDatabaseObject,
)
from backend.agent.intent.semantic_query import (
    SemanticQueryIntent,
    SemanticQueryClass,
    TraversalDirection,
)

logger = logging.getLogger(__name__)


@dataclass
class TraversedEntity:
    name: str
    entity_type: str  # "file", "function", "class", "method", "module", "route", "table"
    location: Optional[str] = None
    line_number: Optional[int] = None
    relationship_role: str = ""  # e.g. "imported_module", "dependent_file", "callee", "caller", "base_class", "subclass", "handler", "accessing_code"
    data: Dict[str, Any] = field(default_factory=dict)
    path: Optional[List[str]] = None
    relationships: Optional[List[str]] = None


@dataclass
class RelationshipTraversalResult:
    query_class: SemanticQueryClass
    direction: TraversalDirection
    target_entity: Optional[Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]]
    target_display_name: str
    target_type: str
    related_entities: List[TraversedEntity] = field(default_factory=list)
    raw_edges: List[FactRelationship] = field(default_factory=list)
    explanation: str = ""
    resolution: str = "STATIC_CONFIRMED"


class FactStoreGraphTraverser:
    """
    Executes directed, analysis-scoped graph traversal on the canonical Fact Store.
    """

    def __init__(self, db: Session, analysis_id: int):
        self.db = db
        self.analysis_id = analysis_id

    def traverse(
        self,
        intent: SemanticQueryIntent,
        target: Optional[Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]]
    ) -> RelationshipTraversalResult:
        """
        Dispatches and executes the appropriate graph traversal based on query intent.
        """
        if not self.analysis_id:
            return RelationshipTraversalResult(
                query_class=intent.query_class,
                direction=intent.direction,
                target_entity=None,
                target_display_name=intent.target_raw_name,
                target_type="unknown",
                explanation="No active analysis provided.",
                resolution="ENTITY_NOT_FOUND",
            )

        if not target:
            return RelationshipTraversalResult(
                query_class=intent.query_class,
                direction=intent.direction,
                target_entity=None,
                target_display_name=intent.target_raw_name,
                target_type="unknown",
                explanation=f"Target '{intent.target_raw_name}' was not found in this repository index.",
                resolution="ENTITY_NOT_FOUND",
            )

        if intent.direction == TraversalDirection.BOTH:
            return self._traverse_both_directions(intent, target)

        # 1. CONTAINMENT
        if intent.query_class == SemanticQueryClass.CONTAINMENT:
            res = self._traverse_containment(target)
        # 2. IMPORTS_FORWARD
        elif intent.query_class == SemanticQueryClass.IMPORTS_FORWARD:
            res = self._traverse_imports_forward(target)
        # 3. IMPORTS_REVERSE
        elif intent.query_class == SemanticQueryClass.IMPORTS_REVERSE:
            res = self._traverse_imports_reverse(target)
        # 4. CALLS_FORWARD
        elif intent.query_class == SemanticQueryClass.CALLS_FORWARD:
            res = self._traverse_calls_forward(target)
        # 5. CALLS_REVERSE
        elif intent.query_class == SemanticQueryClass.CALLS_REVERSE:
            res = self._traverse_calls_reverse(target)
        # 6. INHERITS_FORWARD
        elif intent.query_class == SemanticQueryClass.INHERITS_FORWARD:
            res = self._traverse_inherits_forward(target)
        # 7. INHERITS_REVERSE
        elif intent.query_class == SemanticQueryClass.INHERITS_REVERSE:
            res = self._traverse_inherits_reverse(target)
        # 8. ROUTE_HANDLER
        elif intent.query_class == SemanticQueryClass.ROUTE_HANDLER:
            res = self._traverse_route_handler(target)
        # 9. DATABASE_ACCESS
        elif intent.query_class == SemanticQueryClass.DATABASE_ACCESS:
            res = self._traverse_database_access(target)
        # 10. GENERIC_LOOKUP
        else:
            res = self._traverse_generic_lookup(target)

        res.resolution = "STATIC_CONFIRMED" if res.related_entities else "NO_STATIC_EDGE_FOUND"
        return res

    # ──────────────────────────────────────────────────────────────────────────
    # INDIVIDUAL TRAVERSAL HANDLERS
    # ──────────────────────────────────────────────────────────────────────────

    def _traverse_containment(
        self,
        target: Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]
    ) -> RelationshipTraversalResult:
        related: List[TraversedEntity] = []

        if isinstance(target, FactFile):
            # Fetch symbols declared in file
            symbols = self.db.query(FactSymbol).filter(
                FactSymbol.analysis_id == self.analysis_id,
                FactSymbol.file_id == target.id
            ).order_by(FactSymbol.line_start).all()

            for s in symbols:
                related.append(TraversedEntity(
                    name=s.name,
                    entity_type=s.symbol_type,
                    location=target.path,
                    line_number=s.line_start,
                    relationship_role="defined_symbol",
                    data={"qualified_name": s.qualified_name}
                ))
            return RelationshipTraversalResult(
                query_class=SemanticQueryClass.CONTAINMENT,
                direction=TraversalDirection.FORWARD,
                target_entity=target,
                target_display_name=target.path,
                target_type="file",
                related_entities=related,
                explanation=f"Found {len(related)} symbols declared in '{target.path}'."
            )

        if isinstance(target, FactSymbol):
            # If class, fetch child methods
            symbols = self.db.query(FactSymbol).filter(
                FactSymbol.analysis_id == self.analysis_id,
                FactSymbol.file_id == target.file_id,
                FactSymbol.qualified_name.ilike(f"{target.qualified_name}.%")
            ).order_by(FactSymbol.line_start).all()

            for s in symbols:
                related.append(TraversedEntity(
                    name=s.name,
                    entity_type=s.symbol_type,
                    location=target.file.path if target.file else "",
                    line_number=s.line_start,
                    relationship_role="declared_method",
                    data={"qualified_name": s.qualified_name}
                ))
            return RelationshipTraversalResult(
                query_class=SemanticQueryClass.CONTAINMENT,
                direction=TraversalDirection.FORWARD,
                target_entity=target,
                target_display_name=target.name,
                target_type=target.symbol_type,
                related_entities=related,
                explanation=f"Found {len(related)} members in '{target.name}'."
            )

        return RelationshipTraversalResult(
            query_class=SemanticQueryClass.CONTAINMENT,
            direction=TraversalDirection.FORWARD,
            target_entity=target,
            target_display_name=getattr(target, "name", "target"),
            target_type="unknown",
            related_entities=[],
            explanation="Target does not support containment lookup.",
        )

    def _traverse_imports_forward(
        self,
        target: Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]
    ) -> RelationshipTraversalResult:
        file_rec = target if isinstance(target, FactFile) else (target.file if getattr(target, "file", None) else None)
        if not file_rec:
            return RelationshipTraversalResult(
                query_class=SemanticQueryClass.IMPORTS_FORWARD,
                direction=TraversalDirection.FORWARD,
                target_entity=target,
                target_display_name=getattr(target, "name", str(target)),
                target_type="symbol",
                related_entities=[],
                explanation=f"Target '{getattr(target, 'name', '')}' is not associated with a source file.",
            )

        edges = self.db.query(FactRelationship).filter(
            FactRelationship.analysis_id == self.analysis_id,
            FactRelationship.from_symbol_id == file_rec.id,
            FactRelationship.rel_type == "IMPORTS"
        ).all()

        related: List[TraversedEntity] = []
        for rel in edges:
            mod_name = (rel.to_symbol_id.split("#")[-1] if "#" in rel.to_symbol_id else rel.to_symbol_id.split(":")[-1])
            related.append(TraversedEntity(
                name=mod_name,
                entity_type="module",
                location=file_rec.path,
                line_number=rel.evidence_line,
                relationship_role="imported_module",
                data={"rel_id": rel.id, "to_symbol_id": rel.to_symbol_id}
            ))

        return RelationshipTraversalResult(
            query_class=SemanticQueryClass.IMPORTS_FORWARD,
            direction=TraversalDirection.FORWARD,
            target_entity=file_rec,
            target_display_name=file_rec.path,
            target_type="file",
            related_entities=related,
            raw_edges=edges,
            explanation=f"File '{file_rec.path}' imports {len(related)} modules/packages."
        )

    def _traverse_imports_reverse(
        self,
        target: Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]
    ) -> RelationshipTraversalResult:
        target_path = target.path if isinstance(target, FactFile) else getattr(target, "name", "")
        clean_mod = target_path.replace("/", ".").replace(".py", "").replace(".ts", "").replace(".js", "")
        mod_base = clean_mod.split(".")[-1]

        # Match incoming IMPORTS relationships
        conditions = [FactRelationship.to_symbol_id.ilike(f"%#{clean_mod}")]
        if isinstance(target, FactFile):
            conditions.append(FactRelationship.to_symbol_id == target.id)
        if mod_base != clean_mod:
            conditions.append(FactRelationship.to_symbol_id.ilike(f"%#{mod_base}"))

        edges = self.db.query(FactRelationship).filter(
            FactRelationship.analysis_id == self.analysis_id,
            FactRelationship.rel_type == "IMPORTS",
            or_(*conditions)
        ).all()

        # Find importing files
        from_file_ids = list({e.from_symbol_id for e in edges})
        importing_files = self.db.query(FactFile).filter(
            FactFile.analysis_id == self.analysis_id,
            FactFile.id.in_(from_file_ids)
        ).all() if from_file_ids else []

        related: List[TraversedEntity] = []
        for f in importing_files:
            related.append(TraversedEntity(
                name=f.path,
                entity_type="file",
                location=f.path,
                line_number=1,
                relationship_role="dependent_file",
                data={"file_id": f.id}
            ))

        return RelationshipTraversalResult(
            query_class=SemanticQueryClass.IMPORTS_REVERSE,
            direction=TraversalDirection.REVERSE,
            target_entity=target,
            target_display_name=target_path,
            target_type="file" if isinstance(target, FactFile) else "module",
            related_entities=related,
            raw_edges=edges,
            explanation=f"Found {len(related)} files depending on / importing '{target_path}'."
        )

    def _traverse_calls_forward(
        self,
        target: Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]
    ) -> RelationshipTraversalResult:
        if not isinstance(target, FactSymbol):
            return RelationshipTraversalResult(
                query_class=SemanticQueryClass.CALLS_FORWARD,
                direction=TraversalDirection.FORWARD,
                target_entity=target,
                target_display_name=getattr(target, "name", str(target)),
                target_type="unknown",
                related_entities=[],
                explanation="Calls forward traversal requires a function or method target.",
            )

        edges = self.db.query(FactRelationship).filter(
            FactRelationship.analysis_id == self.analysis_id,
            FactRelationship.from_symbol_id == target.id,
            FactRelationship.rel_type == "CALLS"
        ).all()

        related: List[TraversedEntity] = []
        for rel in edges:
            callee_name = rel.to_symbol_id.split("#")[-1] if "#" in rel.to_symbol_id else rel.to_symbol_id.split(":")[-1]
            callee_name = callee_name.split(".")[-1]
            related.append(TraversedEntity(
                name=callee_name,
                entity_type="function",
                location=target.file.path if target.file else "",
                line_number=rel.evidence_line,
                relationship_role="callee",
                data={"rel_id": rel.id, "to_symbol_id": rel.to_symbol_id}
            ))

        return RelationshipTraversalResult(
            query_class=SemanticQueryClass.CALLS_FORWARD,
            direction=TraversalDirection.FORWARD,
            target_entity=target,
            target_display_name=target.name,
            target_type=target.symbol_type,
            related_entities=related,
            raw_edges=edges,
            explanation=f"Function '{target.name}' invokes {len(related)} functions/methods."
        )

    def _traverse_calls_reverse(
        self,
        target: Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]
    ) -> RelationshipTraversalResult:
        target_name = target.name if isinstance(target, FactSymbol) else getattr(target, "name", str(target))
        target_id = target.id if isinstance(target, FactSymbol) else ""
        target_qname = getattr(target, "qualified_name", target_name)

        conditions = [
            FactRelationship.to_symbol_id == target_id,
            FactRelationship.to_symbol_id.ilike(f"%#{target_qname}"),
            FactRelationship.to_symbol_id.ilike(f"%#{target_name}"),
            FactRelationship.to_symbol_id.ilike(f"%.{target_name}"),
        ]

        edges = self.db.query(FactRelationship).filter(
            FactRelationship.analysis_id == self.analysis_id,
            FactRelationship.rel_type == "CALLS",
            or_(*conditions)
        ).all()

        caller_ids = list({e.from_symbol_id for e in edges})
        caller_symbols = self.db.query(FactSymbol).filter(
            FactSymbol.analysis_id == self.analysis_id,
            FactSymbol.id.in_(caller_ids)
        ).all() if caller_ids else []

        related: List[TraversedEntity] = []
        for s in caller_symbols:
            related.append(TraversedEntity(
                name=s.name,
                entity_type=s.symbol_type,
                location=s.file.path if s.file else "",
                line_number=s.line_start,
                relationship_role="caller",
                data={"symbol_id": s.id}
            ))

        return RelationshipTraversalResult(
            query_class=SemanticQueryClass.CALLS_REVERSE,
            direction=TraversalDirection.REVERSE,
            target_entity=target,
            target_display_name=target_name,
            target_type="function" if isinstance(target, FactSymbol) else "symbol",
            related_entities=related,
            raw_edges=edges,
            explanation=f"Found {len(related)} functions/methods that call '{target_name}'."
        )

    def _traverse_inherits_forward(
        self,
        target: Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]
    ) -> RelationshipTraversalResult:
        if not isinstance(target, FactSymbol):
            return RelationshipTraversalResult(
                query_class=SemanticQueryClass.INHERITS_FORWARD,
                direction=TraversalDirection.FORWARD,
                target_entity=target,
                target_display_name=getattr(target, "name", str(target)),
                target_type="unknown",
                related_entities=[],
                explanation="Inheritance traversal requires a class target.",
            )

        edges = self.db.query(FactRelationship).filter(
            FactRelationship.analysis_id == self.analysis_id,
            FactRelationship.from_symbol_id == target.id,
            FactRelationship.rel_type == "INHERITS"
        ).all()

        related: List[TraversedEntity] = []
        for rel in edges:
            base_name = rel.to_symbol_id.split("#")[-1] if "#" in rel.to_symbol_id else rel.to_symbol_id.split(":")[-1]
            base_name = base_name.split(".")[-1]
            related.append(TraversedEntity(
                name=base_name,
                entity_type="class",
                location=target.file.path if target.file else "",
                line_number=rel.evidence_line,
                relationship_role="base_class",
                data={"rel_id": rel.id, "to_symbol_id": rel.to_symbol_id}
            ))

        return RelationshipTraversalResult(
            query_class=SemanticQueryClass.INHERITS_FORWARD,
            direction=TraversalDirection.FORWARD,
            target_entity=target,
            target_display_name=target.name,
            target_type="class",
            related_entities=related,
            raw_edges=edges,
            explanation=f"Class '{target.name}' inherits from {len(related)} base classes."
        )

    def _traverse_inherits_reverse(
        self,
        target: Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]
    ) -> RelationshipTraversalResult:
        target_name = target.name if isinstance(target, FactSymbol) else getattr(target, "name", str(target))
        target_id = target.id if isinstance(target, FactSymbol) else ""
        target_qname = getattr(target, "qualified_name", target_name)

        conditions = [
            FactRelationship.to_symbol_id == target_id,
            FactRelationship.to_symbol_id.ilike(f"%#{target_qname}"),
            FactRelationship.to_symbol_id.ilike(f"%#{target_name}"),
            FactRelationship.to_symbol_id.ilike(f"%.{target_name}"),
        ]

        edges = self.db.query(FactRelationship).filter(
            FactRelationship.analysis_id == self.analysis_id,
            FactRelationship.rel_type == "INHERITS",
            or_(*conditions)
        ).all()

        derived_ids = list({e.from_symbol_id for e in edges})
        derived_symbols = self.db.query(FactSymbol).filter(
            FactSymbol.analysis_id == self.analysis_id,
            FactSymbol.id.in_(derived_ids)
        ).all() if derived_ids else []

        related: List[TraversedEntity] = []
        for s in derived_symbols:
            related.append(TraversedEntity(
                name=s.name,
                entity_type=s.symbol_type,
                location=s.file.path if s.file else "",
                line_number=s.line_start,
                relationship_role="subclass",
                data={"symbol_id": s.id}
            ))

        return RelationshipTraversalResult(
            query_class=SemanticQueryClass.INHERITS_REVERSE,
            direction=TraversalDirection.REVERSE,
            target_entity=target,
            target_display_name=target_name,
            target_type="class",
            related_entities=related,
            raw_edges=edges,
            explanation=f"Found {len(related)} classes extending / inheriting from '{target_name}'."
        )

    def _traverse_route_handler(
        self,
        target: Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]
    ) -> RelationshipTraversalResult:
        route_rec = target if isinstance(target, FactRoute) else None
        if not route_rec:
            return RelationshipTraversalResult(
                query_class=SemanticQueryClass.ROUTE_HANDLER,
                direction=TraversalDirection.FORWARD,
                target_entity=target,
                target_display_name=getattr(target, "name", str(target)),
                target_type="unknown",
                related_entities=[],
                explanation="Route lookup requires a valid FactRoute entity.",
            )

        handler_sym = None
        if route_rec.handler_symbol_id:
            handler_sym = self.db.query(FactSymbol).filter(
                FactSymbol.analysis_id == self.analysis_id,
                or_(
                    FactSymbol.id == route_rec.handler_symbol_id,
                    FactSymbol.id == f"{self.analysis_id}:{route_rec.handler_symbol_id}",
                    FactSymbol.id.ilike(f"%{route_rec.handler_symbol_id.split(':')[-1]}"),
                )
            ).first()

        if not handler_sym:
            # Check EXPOSES relationship
            rel = self.db.query(FactRelationship).filter(
                FactRelationship.analysis_id == self.analysis_id,
                or_(
                    FactRelationship.to_symbol_id == route_rec.id,
                    FactRelationship.to_symbol_id.ilike(f"%{route_rec.path}%"),
                ),
                FactRelationship.rel_type == "EXPOSES"
            ).first()
            if rel:
                handler_sym = self.db.query(FactSymbol).filter(
                    FactSymbol.analysis_id == self.analysis_id,
                    FactSymbol.id == rel.from_symbol_id
                ).first()

        related: List[TraversedEntity] = []
        if handler_sym:
            related.append(TraversedEntity(
                name=handler_sym.name,
                entity_type=handler_sym.symbol_type,
                location=handler_sym.file.path if handler_sym.file else "",
                line_number=handler_sym.line_start,
                relationship_role="route_handler",
                data={"route_path": route_rec.path, "route_method": route_rec.method}
            ))

        return RelationshipTraversalResult(
            query_class=SemanticQueryClass.ROUTE_HANDLER,
            direction=TraversalDirection.FORWARD,
            target_entity=route_rec,
            target_display_name=f"{route_rec.method} {route_rec.path}",
            target_type="route",
            related_entities=related,
            explanation=f"Route '{route_rec.method} {route_rec.path}' is handled by '{handler_sym.name}'." if handler_sym else f"No handler mapped for route '{route_rec.method} {route_rec.path}'."
        )

    def _traverse_database_access(
        self,
        target: Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]
    ) -> RelationshipTraversalResult:
        table_name = target.name if isinstance(target, FactDatabaseObject) else getattr(target, "name", str(target))
        table_id = target.symbol_id if isinstance(target, FactDatabaseObject) and target.symbol_id else (target.id if isinstance(target, FactSymbol) else "")

        conditions = [
            FactRelationship.to_symbol_id == table_id,
            FactRelationship.from_symbol_id == table_id,
            FactRelationship.to_symbol_id.ilike(f"%#{table_name}"),
            FactRelationship.from_symbol_id.ilike(f"%#{table_name}"),
            FactRelationship.to_symbol_id.ilike(f"%{table_name}%"),
        ]

        edges = self.db.query(FactRelationship).filter(
            FactRelationship.analysis_id == self.analysis_id,
            FactRelationship.rel_type.in_(["USES", "QUERIES", "READS", "WRITES", "IMPORTS"]),
            or_(*conditions)
        ).all()

        accessing_ids = list({e.from_symbol_id for e in edges if e.from_symbol_id != table_id} | {e.to_symbol_id for e in edges if e.to_symbol_id != table_id})
        accessing_symbols = self.db.query(FactSymbol).filter(
            FactSymbol.analysis_id == self.analysis_id,
            FactSymbol.id.in_(accessing_ids)
        ).all() if accessing_ids else []

        accessing_files = self.db.query(FactFile).filter(
            FactFile.analysis_id == self.analysis_id,
            FactFile.id.in_(accessing_ids)
        ).all() if accessing_ids else []

        related: List[TraversedEntity] = []
        for s in accessing_symbols:
            related.append(TraversedEntity(
                name=s.name,
                entity_type=s.symbol_type,
                location=s.file.path if s.file else "",
                line_number=s.line_start,
                relationship_role="accessing_code",
                data={"symbol_id": s.id}
            ))
        for f in accessing_files:
            related.append(TraversedEntity(
                name=f.path,
                entity_type="file",
                location=f.path,
                line_number=1,
                relationship_role="accessing_file",
                data={"file_id": f.id}
            ))

        db_tables = self.db.query(FactDatabaseObject).filter(
            FactDatabaseObject.analysis_id == self.analysis_id,
            or_(
                FactDatabaseObject.symbol_id.in_(accessing_ids),
                FactDatabaseObject.name.in_([e.to_symbol_id.split("#")[-1] for e in edges if e.to_symbol_id != table_id]),
                FactDatabaseObject.name.in_([e.from_symbol_id.split("#")[-1] for e in edges if e.from_symbol_id != table_id]),
            )
        ).all() if edges else []
        for dt in db_tables:
            if dt.name == table_name or dt.symbol_id == table_id:
                continue
            loc = ""
            line_num = 1
            if dt.symbol_id:
                sym = self.db.query(FactSymbol).filter(
                    FactSymbol.analysis_id == self.analysis_id,
                    FactSymbol.id == dt.symbol_id
                ).first()
                if sym:
                    loc = sym.file.path if sym.file else ""
                    line_num = sym.line_start
            related.append(TraversedEntity(
                name=dt.name,
                entity_type=dt.object_type or "database_table",
                location=loc,
                line_number=line_num,
                relationship_role="accessed_table",
                data={"table_id": dt.id, "object_type": dt.object_type}
            ))

        resolution = "STATIC_CONFIRMED" if related else "NO_STATIC_EDGE_FOUND"
        return RelationshipTraversalResult(
            query_class=SemanticQueryClass.DATABASE_ACCESS,
            direction=TraversalDirection.REVERSE if isinstance(target, FactDatabaseObject) else TraversalDirection.FORWARD,
            target_entity=target,
            target_display_name=table_name,
            target_type="database_table" if isinstance(target, FactDatabaseObject) else "model",
            related_entities=related,
            raw_edges=edges,
            explanation=f"Found {len(related)} database/code relationships for '{table_name}'.",
            resolution=resolution,
        )

    def _traverse_generic_lookup(
        self,
        target: Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]
    ) -> RelationshipTraversalResult:
        name = getattr(target, "name", getattr(target, "path", "target"))
        entity_type = "file" if isinstance(target, FactFile) else ("symbol" if isinstance(target, FactSymbol) else "entity")
        loc = target.path if isinstance(target, FactFile) else (target.file.path if getattr(target, "file", None) else "")
        line = target.line_start if hasattr(target, "line_start") else 1

        related = [
            TraversedEntity(
                name=name,
                entity_type=entity_type,
                location=loc,
                line_number=line,
                relationship_role="matched_entity",
            )
        ]
        return RelationshipTraversalResult(
            query_class=SemanticQueryClass.GENERIC_LOOKUP,
            direction=TraversalDirection.FORWARD,
            target_entity=target,
            target_display_name=name,
            target_type=entity_type,
            related_entities=related,
            explanation=f"Located '{name}' ({entity_type}).",
            resolution="STATIC_CONFIRMED",
        )

    def _traverse_both_directions(
        self,
        intent: SemanticQueryIntent,
        target: Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]
    ) -> RelationshipTraversalResult:
        """Execute both forward and reverse traversal and merge results."""
        fwd_class = intent.query_class
        rev_class = intent.query_class
        if intent.query_class in (SemanticQueryClass.CALLS_FORWARD, SemanticQueryClass.CALLS_REVERSE):
            fwd_class, rev_class = SemanticQueryClass.CALLS_FORWARD, SemanticQueryClass.CALLS_REVERSE
        elif intent.query_class in (SemanticQueryClass.IMPORTS_FORWARD, SemanticQueryClass.IMPORTS_REVERSE):
            fwd_class, rev_class = SemanticQueryClass.IMPORTS_FORWARD, SemanticQueryClass.IMPORTS_REVERSE
        elif intent.query_class in (SemanticQueryClass.INHERITS_FORWARD, SemanticQueryClass.INHERITS_REVERSE):
            fwd_class, rev_class = SemanticQueryClass.INHERITS_FORWARD, SemanticQueryClass.INHERITS_REVERSE

        fwd_intent = SemanticQueryIntent(
            query_class=fwd_class,
            target_raw_name=intent.target_raw_name,
            direction=TraversalDirection.FORWARD,
            confidence=intent.confidence,
        )
        rev_intent = SemanticQueryIntent(
            query_class=rev_class,
            target_raw_name=intent.target_raw_name,
            direction=TraversalDirection.REVERSE,
            confidence=intent.confidence,
        )

        res_fwd = self.traverse(fwd_intent, target)
        res_rev = self.traverse(rev_intent, target)

        merged_related: List[TraversedEntity] = list(res_fwd.related_entities)
        seen_keys = {
            (e.name, e.relationship_role, e.location)
            for e in merged_related
        }
        for e in res_rev.related_entities:
            key = (e.name, e.relationship_role, e.location)
            if key not in seen_keys:
                seen_keys.add(key)
                merged_related.append(e)

        merged_edges = list(res_fwd.raw_edges)
        edge_ids = {edge.id for edge in merged_edges}
        for edge in res_rev.raw_edges:
            if edge.id not in edge_ids:
                edge_ids.add(edge.id)
                merged_edges.append(edge)

        target_name = getattr(target, "name", getattr(target, "path", intent.target_raw_name))
        resolution = "STATIC_CONFIRMED" if merged_related else "NO_STATIC_EDGE_FOUND"
        explanation = f"Found {len(merged_related)} bidirectional relationships for '{target_name}' ({len(res_fwd.related_entities)} outgoing, {len(res_rev.related_entities)} incoming)."

        return RelationshipTraversalResult(
            query_class=intent.query_class,
            direction=TraversalDirection.BOTH,
            target_entity=target,
            target_display_name=target_name,
            target_type=res_fwd.target_type or res_rev.target_type,
            related_entities=merged_related,
            raw_edges=merged_edges,
            explanation=explanation,
            resolution=resolution,
        )

    def _map_type_direction_to_query_class(self, relationship_type: str, direction: str) -> SemanticQueryClass:
        rt = (relationship_type or "GENERIC").upper()
        d = (direction or "FORWARD").upper()
        if rt == "CALLS":
            return SemanticQueryClass.CALLS_FORWARD if d != "REVERSE" else SemanticQueryClass.CALLS_REVERSE
        elif rt == "IMPORTS":
            return SemanticQueryClass.IMPORTS_FORWARD if d != "REVERSE" else SemanticQueryClass.IMPORTS_REVERSE
        elif rt == "INHERITS":
            return SemanticQueryClass.INHERITS_FORWARD if d != "REVERSE" else SemanticQueryClass.INHERITS_REVERSE
        elif rt == "CONTAINS":
            return SemanticQueryClass.CONTAINMENT
        elif rt == "ROUTE_HANDLER":
            return SemanticQueryClass.ROUTE_HANDLER
        elif rt == "DATABASE_ACCESS":
            return SemanticQueryClass.DATABASE_ACCESS
        else:
            return SemanticQueryClass.GENERIC_LOOKUP

    def traverse_bounded(
        self,
        target: Optional[Union[FactFile, FactSymbol, FactRoute, FactDatabaseObject]],
        relationship_type: str = "GENERIC",
        direction: str = "FORWARD",
        scope: str = "LOCAL",
        depth: int = 1,
        limit: int = 15,
        target_raw_name: str = "",
    ) -> RelationshipTraversalResult:
        """
        Executes bounded, scope-aware graph traversal.
        - LOCAL: 1-hop direct relationships
        - NEIGHBORHOOD: Bounded multi-hop traversal (depth 1 to 3)
        - GLOBAL: Repository-wide relationship traversal (depth 1 to 3)
        """
        scope_norm = (scope or "LOCAL").upper()
        dir_norm = (direction or "FORWARD").upper()
        rel_type_norm = (relationship_type or "GENERIC").upper()

        if dir_norm not in ("FORWARD", "REVERSE", "BOTH"):
            dir_norm = "FORWARD"

        if scope_norm == "LOCAL":
            max_depth = 1
        else:
            max_depth = max(1, min(int(depth or 1), 3))

        max_limit = max(1, min(int(limit or 15), 50))

        if not target:
            return RelationshipTraversalResult(
                query_class=self._map_type_direction_to_query_class(rel_type_norm, dir_norm),
                direction=TraversalDirection(dir_norm),
                target_entity=None,
                target_display_name=target_raw_name,
                target_type="unknown",
                explanation=f"Target '{target_raw_name}' was not found in this repository index.",
                resolution="ENTITY_NOT_FOUND",
            )

        root_name = getattr(target, "name", getattr(target, "path", target_raw_name or "target"))

        if max_depth == 1:
            intent = SemanticQueryIntent(
                query_class=self._map_type_direction_to_query_class(rel_type_norm, dir_norm),
                target_raw_name=root_name,
                direction=TraversalDirection(dir_norm),
                confidence=1.0,
            )
            res = self.traverse(intent, target)
            for e in res.related_entities:
                if not e.path:
                    e.path = [root_name, e.name]
                if not e.relationships:
                    e.relationships = [rel_type_norm]
            res.related_entities = res.related_entities[:max_limit]
            res.resolution = "STATIC_CONFIRMED" if res.related_entities else "NO_STATIC_EDGE_FOUND"
            return res

        # Multi-hop BFS traversal (depth 2 or 3)
        queue: List[tuple] = [(target, [root_name], [], 0)]
        root_key = getattr(target, "id", root_name)
        visited_keys = {root_key}
        all_discovered: List[TraversedEntity] = []
        all_edges: List[FactRelationship] = []

        while queue and len(all_discovered) < max_limit:
            curr_target, curr_path, curr_rels, curr_d = queue.pop(0)
            if curr_d >= max_depth:
                continue

            step_intent = SemanticQueryIntent(
                query_class=self._map_type_direction_to_query_class(rel_type_norm, dir_norm),
                target_raw_name=getattr(curr_target, "name", getattr(curr_target, "path", "")),
                direction=TraversalDirection(dir_norm),
                confidence=1.0,
            )
            step_res = self.traverse(step_intent, curr_target)
            all_edges.extend(step_res.raw_edges)

            for ent in step_res.related_entities:
                ent_key = ent.data.get("symbol_id") or ent.data.get("file_id") or ent.name
                if ent.name in curr_path:
                    continue  # Prevent cycle

                child_path = curr_path + [ent.name]
                child_rels = curr_rels + [rel_type_norm]
                ent.path = child_path
                ent.relationships = child_rels
                all_discovered.append(ent)

                if len(all_discovered) >= max_limit:
                    break

                if curr_d + 1 < max_depth and ent_key not in visited_keys:
                    visited_keys.add(ent_key)
                    next_node = None
                    if ent.data.get("symbol_id"):
                        next_node = self.db.query(FactSymbol).filter(
                            FactSymbol.analysis_id == self.analysis_id,
                            FactSymbol.id == ent.data["symbol_id"]
                        ).first()
                    elif ent.data.get("file_id"):
                        next_node = self.db.query(FactFile).filter(
                            FactFile.analysis_id == self.analysis_id,
                            FactFile.id == ent.data["file_id"]
                        ).first()
                    else:
                        next_node = self.db.query(FactSymbol).filter(
                            FactSymbol.analysis_id == self.analysis_id,
                            FactSymbol.name == ent.name
                        ).first()
                    if next_node:
                        queue.append((next_node, child_path, child_rels, curr_d + 1))

        resolution = "STATIC_CONFIRMED" if all_discovered else "NO_STATIC_EDGE_FOUND"
        explanation = (
            f"Discovered {len(all_discovered)} entities across {max_depth}-hop {scope_norm} traversal "
            f"for '{root_name}' ({rel_type_norm}, {dir_norm})."
        )
        return RelationshipTraversalResult(
            query_class=self._map_type_direction_to_query_class(rel_type_norm, dir_norm),
            direction=TraversalDirection(dir_norm),
            target_entity=target,
            target_display_name=root_name,
            target_type=getattr(target, "symbol_type", "file" if isinstance(target, FactFile) else "entity"),
            related_entities=all_discovered,
            raw_edges=all_edges,
            explanation=explanation,
            resolution=resolution,
        )
