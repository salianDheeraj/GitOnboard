from sqlalchemy.orm import Session
from backend.models.fact_store import (
    SymbolRecord, RelationshipRecord, RouteRecord, 
    CapabilityRecord, CapabilityMemberRecord, EvidenceRecord
)

class FactStore:
    def __init__(self, db: Session):
        self.db = db

    def save_symbols(self, symbols: list[dict]):
        for sym in symbols:
            record = SymbolRecord(
                id=sym["stable_id"],
                file_id=sym["file_id"],
                name=sym["name"],
                qualified_name=sym["qualified_name"],
                symbol_type=sym["symbol_type"],
                line_start=sym["line_start"],
                line_end=sym["line_end"],
                signature_hash=sym.get("signature_hash"),
                symbol_metadata=sym.get("metadata", {})
            )
            self.db.merge(record)
        self.db.commit()

    def save_relationships(self, relationships: list[dict]):
        for rel in relationships:
            record = RelationshipRecord(
                id=rel["id"],
                from_symbol_id=rel["from_symbol_id"],
                to_symbol_id=rel["to_symbol_id"],
                rel_type=rel["rel_type"],
                evidence_line=rel.get("evidence_line"),
                evidence_snippet=rel.get("evidence_snippet"),
                status=rel.get("status", "CONFIRMED")
            )
            self.db.merge(record)
        self.db.commit()

    def save_routes(self, routes: list[dict]):
        for r in routes:
            record = RouteRecord(
                id=r["id"],
                symbol_id=r.get("symbol_id"),
                method=r["method"],
                path=r["path"],
                handler_symbol_id=r["handler_symbol_id"]
            )
            self.db.merge(record)
        self.db.commit()