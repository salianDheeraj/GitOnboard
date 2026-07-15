import ast
from typing import Dict, List, Optional
from .base import BaseAnalyzer
from ..parser.providers.base import ParsedFile
from ...rim.repository import RepositoryModel
from ...rim.relationship import Relationship
from ...rim.enums import EntityType, RelationshipType
from ...rim.identity import generate_entity_id, generate_relationship_id

class PythonImportVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.relationships: List[Relationship] = []
        self.file_id = generate_entity_id(EntityType.FILE, self.file_path, self.file_path)

    def _resolve_module_path(self, module_name: str, level: int = 0) -> str:
        # Simplistic resolution for now. 
        # A true resolve requires checking repository structure to see if it's local.
        if level > 0:
            parts = self.file_path.split("/")[:-level]
            if module_name:
                parts.append(module_name.replace(".", "/"))
            return "/".join(parts) + ".py"
        return module_name.replace(".", "/") + ".py"

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            # We don't resolve external imports properly yet, just mark dependency on module
            mod_id = generate_entity_id(EntityType.MODULE, self.file_path, alias.name)
            rel = Relationship(
                id=generate_relationship_id(RelationshipType.IMPORTS, self.file_id, mod_id),
                type=RelationshipType.IMPORTS,
                source_id=self.file_id,
                target_id=mod_id,
                metadata={"module": alias.name}
            )
            self.relationships.append(rel)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            mod_id = generate_entity_id(EntityType.MODULE, self.file_path, node.module)
            rel = Relationship(
                id=generate_relationship_id(RelationshipType.IMPORTS, self.file_id, mod_id),
                type=RelationshipType.IMPORTS,
                source_id=self.file_id,
                target_id=mod_id,
                metadata={"module": node.module, "level": node.level}
            )
            self.relationships.append(rel)
        self.generic_visit(node)

class ImportAnalyzer(BaseAnalyzer):
    name = "ImportAnalyzer"
    supported_languages = ["Python"]

    def analyze(self, repository: RepositoryModel, asts: Dict[str, ParsedFile]) -> None:
        for file_path, parsed in asts.items():
            if parsed.language not in self.supported_languages or not parsed.ast:
                continue
                
            visitor = PythonImportVisitor(file_path)
            visitor.visit(parsed.ast)
            
            for rel in visitor.relationships:
                # We skip adding the target entity if it doesn't exist to keep things clean,
                # but typically an import analyzer should create external module entities.
                # For this MVP, we will inject dummy MODULE entities if they don't exist.
                if rel.target_id not in repository.entities:
                    # Create external module entity
                    from ...rim.entity import Entity
                    from ...rim.location import SourceLocation
                    
                    repository.entities[rel.target_id] = Entity(
                        id=rel.target_id,
                        type=EntityType.MODULE,
                        name=rel.metadata.get("module", "unknown"),
                        location=SourceLocation(repository_path="external", start_line=1, end_line=1, language="Python")
                    )
                repository.relationships[rel.id] = rel
