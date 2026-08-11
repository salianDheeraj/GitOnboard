from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=True)
    root_path = Column(String, nullable=False)
    commit_hash = Column(String, nullable=True)
    analyzed_at = Column(DateTime, default=datetime.utcnow)
    parser_version = Column(String, default="1.0")

class FileRecord(Base):
    __tablename__ = "files"

    id = Column(String, primary_key=True)
    repo_id = Column(String, ForeignKey("repositories.id"), nullable=False)
    path = Column(String, nullable=False)
    language = Column(String, nullable=False)
    content_hash = Column(String, nullable=False)
    last_modified = Column(DateTime, default=datetime.utcnow)

class SymbolRecord(Base):
    __tablename__ = "symbols"

    id = Column(String, primary_key=True)  # Stable ID hash
    file_id = Column(String, ForeignKey("files.id"), nullable=False)
    name = Column(String, nullable=False)
    qualified_name = Column(String, nullable=False)
    symbol_type = Column(String, nullable=False) # function, class, method, variable
    line_start = Column(Integer, nullable=False)
    line_end = Column(Integer, nullable=False)
    signature_hash = Column(String, nullable=True)
    symbol_metadata = Column(JSON, nullable=True)

class RelationshipRecord(Base):
    __tablename__ = "relationships"

    id = Column(String, primary_key=True)
    from_symbol_id = Column(String, ForeignKey("symbols.id"), nullable=False)
    to_symbol_id = Column(String, ForeignKey("symbols.id"), nullable=False)
    rel_type = Column(String, nullable=False) # CONTAINS, CALLS, IMPORTS, INHERITS, READS, WRITES, QUERIES
    evidence_line = Column(Integer, nullable=True)
    evidence_snippet = Column(Text, nullable=True)
    status = Column(String, default="CONFIRMED") # CONFIRMED, INFERRED, UNRESOLVED
    created_at = Column(DateTime, default=datetime.utcnow)

class RouteRecord(Base):
    __tablename__ = "routes"

    id = Column(String, primary_key=True)
    symbol_id = Column(String, ForeignKey("symbols.id"), nullable=False)
    method = Column(String, nullable=False)
    path = Column(String, nullable=False)
    handler_symbol_id = Column(String, ForeignKey("symbols.id"), nullable=False)

class DatabaseObjectRecord(Base):
    __tablename__ = "database_objects"

    id = Column(String, primary_key=True)
    symbol_id = Column(String, ForeignKey("symbols.id"), nullable=False)
    object_type = Column(String, nullable=False) # table, column, model
    name = Column(String, nullable=False)

class CapabilityRecord(Base):
    __tablename__ = "capabilities"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False) # Authentication, CRUD, FileUpload, Background Tasks
    capability_type = Column(String, nullable=False)
    status = Column(String, default="CONFIRMED")
    evidence_summary = Column(Text, nullable=True)

class CapabilityMemberRecord(Base):
    __tablename__ = "capability_members"

    id = Column(String, primary_key=True)
    capability_id = Column(String, ForeignKey("capabilities.id"), nullable=False)
    symbol_id = Column(String, ForeignKey("symbols.id"), nullable=False)
    role = Column(String, nullable=False) # entry_point, service, repository, table
    evidence_id = Column(String, ForeignKey("evidence.id"), nullable=True)

class EvidenceRecord(Base):
    __tablename__ = "evidence"

    id = Column(String, primary_key=True)
    fact_type = Column(String, nullable=False)
    symbol_id = Column(String, ForeignKey("symbols.id"), nullable=False)
    details = Column(Text, nullable=False)
    location = Column(String, nullable=False)