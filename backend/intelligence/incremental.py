from typing import List, Dict, Any
from sqlalchemy.orm import Session
from backend.models.fact_store import (
    FileRecord, SymbolRecord, RelationshipRecord, 
    RouteRecord, CapabilityRecord, CapabilityMemberRecord
)
from backend.intelligence.store.fact_store import FactStore
from backend.intelligence.capabilities.rule_engine import DeterministicCapabilityEngine

class IncrementalUpdateEngine:
    """
    Layer 7: Incremental Update Pipeline
    Handles git diff detection, fact diffing, cascade deletions, and incremental RIM updates.
    """
    def __init__(self, db: Session, repo_id: str):
        self.db = db
        self.repo_id = repo_id
        self.fact_store = FactStore(db)

    def process_file_changes(self, changed_file_paths: List[str], new_file_facts: List[Dict[str, Any]]):
        """
        Processes changed or deleted files incrementally.
        """
        for file_path in changed_file_paths:
            file_id = f"{self.repo_id}:{file_path}"
            
            # 1. Cascade Delete Stale Symbols & Relationships for Changed Files
            self._cascade_delete_file_facts(file_id)

        # 2. Persist Newly Extracted Facts
        symbols = [f for f in new_file_facts if "symbol_type" in f]
        routes = [f for f in new_file_facts if "method" in f]
        relationships = [f for f in new_file_facts if "rel_type" in f]

        if symbols:
            self.fact_store.save_symbols(symbols)
        if routes:
            self.fact_store.save_routes(routes)
        if relationships:
            self.fact_store.save_relationships(relationships)

        # 3. Re-evaluate Affected Capabilities Only
        cap_engine = DeterministicCapabilityEngine(self.db, self.repo_id)
        cap_engine.run_all_detectors()

    def _cascade_delete_file_facts(self, file_id: str):
        """Deletes symbols and dependent relationships associated with a modified file."""
        # Find all symbol IDs belonging to this file
        symbols = self.db.query(SymbolRecord).filter(SymbolRecord.file_id == file_id).all()
        symbol_ids = [s.id for s in symbols]

        if symbol_ids:
            # Delete relationships pointing to or originating from these symbols
            self.db.query(RelationshipRecord).filter(
                (RelationshipRecord.from_symbol_id.in_(symbol_ids)) | 
                (RelationshipRecord.to_symbol_id.in_(symbol_ids))
            ).delete(synchronize_session=False)

            # Delete capability member links
            self.db.query(CapabilityMemberRecord).filter(
                CapabilityMemberRecord.symbol_id.in_(symbol_ids)
            ).delete(synchronize_session=False)

            # Delete route records tied to handler symbols
            self.db.query(RouteRecord).filter(
                RouteRecord.handler_symbol_id.in_(symbol_ids)
            ).delete(synchronize_session=False)

            # Delete the symbols themselves
            self.db.query(SymbolRecord).filter(
                SymbolRecord.file_id == file_id
            ).delete(synchronize_session=False)

            self.db.commit()