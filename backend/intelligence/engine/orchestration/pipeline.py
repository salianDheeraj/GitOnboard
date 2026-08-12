from pathlib import Path
from sqlalchemy.orm import Session
from typing import Optional

from ..scanner.scanner import RepositoryScanner
from ..parser.manager import ASTParserManager
from ..analyzers.symbol import SymbolAnalyzer
from ..analyzers.route import RouteAnalyzer
from ..analyzers.callgraph import CallGraphAnalyzer
from ..analyzers.registry import AnalyzerRegistry
from ...rim.repository import RepositoryModel
from ...rim.metadata import RepositoryMetadata
from ...rim.validation import RIMValidator
from backend.intelligence.store.fact_store import FactStore
from backend.intelligence.capabilities.rule_engine import DeterministicCapabilityEngine

class AnalysisEngine:
    """
    Orchestrates the deterministic extraction pipeline.
    """
    def __init__(self, target_dir: str, registry: AnalyzerRegistry):
        self.target_dir = str(Path(target_dir).resolve())
        self.registry = registry
        
    def run(self, repo_name: str) -> RepositoryModel:
        # 1. Scan Repository
        scanner = RepositoryScanner(self.target_dir)
        manifest = scanner.scan()
        
        # Initialize RIM
        model = RepositoryModel(
            metadata=RepositoryMetadata(
                name=repo_name,
                path=self.target_dir,
                languages=manifest.languages
            )
        )
        
        # Pre-populate FILE entities for all scanned files
        from ...rim.enums import EntityType
        from ...rim.entity import Entity
        from ...rim.location import SourceLocation
        from ...rim.identity import generate_entity_id

        for repo_file in manifest.files:
            file_id = generate_entity_id(EntityType.FILE, repo_file.path, repo_file.path)
            if file_id not in model.entities:
                full_p = Path(self.target_dir) / repo_file.path
                line_count = 0
                if full_p.exists() and full_p.is_file():
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="ignore") as fh:
                            line_count = sum(1 for _ in fh)
                    except Exception:
                        line_count = 0

                model.entities[file_id] = Entity(
                    id=file_id,
                    type=EntityType.FILE,
                    name=repo_file.name,
                    qualified_name=repo_file.path,
                    location=SourceLocation(
                        repository_path=repo_file.path,
                        start_line=1,
                        end_line=max(1, line_count),
                        language=repo_file.language
                    ),
                    metadata={"size": repo_file.size, "is_supported": True}
                )
        
        # 2. Parse ASTs
        parser_manager = ASTParserManager(self.target_dir)
        asts = parser_manager.parse_manifest(manifest)
        
        # 3. Execute Analyzers
        for analyzer in self.registry.get_all():
            analyzer.analyze(model, asts)
            
        # 4. Validate RIM
        validator = RIMValidator(model)
        validator.validate()
            
        return model


class AnalysisPipeline:
    """
    Orchestrates the complete deterministic extraction pipeline:
    Scanning -> AST Parsing -> Fact Extraction -> Fact Store Persistence -> Capability Detection
    """
    def __init__(self, db_session: Session):
        self.db = db_session
        self.fact_store = FactStore(db_session)

    def run_analysis(self, repo_id: str, repo_path: str):
        target_dir = str(Path(repo_path).resolve())

        # 1. Scan Repository
        scanner = RepositoryScanner(target_dir)
        manifest = scanner.scan()

        # 2. Parse ASTs
        parser_manager = ASTParserManager(target_dir)
        asts = parser_manager.parse_manifest(manifest)

        # 3. Extract Facts via Analyzers
        symbol_analyzer = SymbolAnalyzer(repo_id, target_dir)
        route_analyzer = RouteAnalyzer(repo_id, target_dir)
        callgraph_analyzer = CallGraphAnalyzer(repo_id, target_dir)

        symbols = symbol_analyzer.extract_symbols(asts)
        routes = route_analyzer.extract_routes(asts, symbols)
        relationships = callgraph_analyzer.extract_relationships(asts, symbols)

        # 4. Persist Facts directly into Relational Fact Store Tables
        self.fact_store.save_symbols(symbols)
        self.fact_store.save_relationships(relationships)
        self.fact_store.save_routes(routes)

        # 5. Run Deterministic Capability Detection
        cap_engine = DeterministicCapabilityEngine(self.db, repo_id)
        cap_engine.run_all_detectors()