from sqlalchemy.orm import Session
from backend.models.fact_store import (
    SymbolRecord, RelationshipRecord, RouteRecord, 
    CapabilityRecord, CapabilityMemberRecord, EvidenceRecord
)

class FactStore:
    BATCH_SIZE = 500

    def __init__(self, db: Session):
        self.db = db

    def save_symbols(self, symbols: list[dict]):
        if not symbols:
            return
        for i in range(0, len(symbols), self.BATCH_SIZE):
            batch = symbols[i : i + self.BATCH_SIZE]
            batch_ids = [s["stable_id"] for s in batch]
            existing_ids = set(
                r[0] for r in self.db.query(SymbolRecord.id).filter(SymbolRecord.id.in_(batch_ids)).all()
            )
            new_records = []
            for sym in batch:
                st_id = sym["stable_id"]
                if st_id in existing_ids:
                    record = SymbolRecord(
                        id=st_id,
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
                else:
                    new_records.append(SymbolRecord(
                        id=st_id,
                        file_id=sym["file_id"],
                        name=sym["name"],
                        qualified_name=sym["qualified_name"],
                        symbol_type=sym["symbol_type"],
                        line_start=sym["line_start"],
                        line_end=sym["line_end"],
                        signature_hash=sym.get("signature_hash"),
                        symbol_metadata=sym.get("metadata", {})
                    ))
            if new_records:
                self.db.add_all(new_records)
            self.db.commit()

    def save_relationships(self, relationships: list[dict]):
        if not relationships:
            return
        for i in range(0, len(relationships), self.BATCH_SIZE):
            batch = relationships[i : i + self.BATCH_SIZE]
            batch_ids = [r["id"] for r in batch]
            existing_ids = set(
                r[0] for r in self.db.query(RelationshipRecord.id).filter(RelationshipRecord.id.in_(batch_ids)).all()
            )
            new_records = []
            for rel in batch:
                rel_id = rel["id"]
                if rel_id in existing_ids:
                    record = RelationshipRecord(
                        id=rel_id,
                        from_symbol_id=rel["from_symbol_id"],
                        to_symbol_id=rel["to_symbol_id"],
                        rel_type=rel["rel_type"],
                        evidence_line=rel.get("evidence_line"),
                        evidence_snippet=rel.get("evidence_snippet"),
                        status=rel.get("status", "CONFIRMED")
                    )
                    self.db.merge(record)
                else:
                    new_records.append(RelationshipRecord(
                        id=rel_id,
                        from_symbol_id=rel["from_symbol_id"],
                        to_symbol_id=rel["to_symbol_id"],
                        rel_type=rel["rel_type"],
                        evidence_line=rel.get("evidence_line"),
                        evidence_snippet=rel.get("evidence_snippet"),
                        status=rel.get("status", "CONFIRMED")
                    ))
            if new_records:
                self.db.add_all(new_records)
            self.db.commit()

    def save_routes(self, routes: list[dict]):
        if not routes:
            return
        for i in range(0, len(routes), self.BATCH_SIZE):
            batch = routes[i : i + self.BATCH_SIZE]
            batch_ids = [r["id"] for r in batch]
            existing_ids = set(
                r[0] for r in self.db.query(RouteRecord.id).filter(RouteRecord.id.in_(batch_ids)).all()
            )
            new_records = []
            for r in batch:
                route_id = r["id"]
                if route_id in existing_ids:
                    record = RouteRecord(
                        id=route_id,
                        symbol_id=r.get("symbol_id"),
                        method=r["method"],
                        path=r["path"],
                        handler_symbol_id=r["handler_symbol_id"]
                    )
                    self.db.merge(record)
                else:
                    new_records.append(RouteRecord(
                        id=route_id,
                        symbol_id=r.get("symbol_id"),
                        method=r["method"],
                        path=r["path"],
                        handler_symbol_id=r["handler_symbol_id"]
                    ))
            if new_records:
                self.db.add_all(new_records)
            self.db.commit()