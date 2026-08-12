import ast
from typing import Dict, List, Optional
from .base import BaseAnalyzer
from ..parser.providers.base import ParsedFile
from ...rim.repository import RepositoryModel
from ...rim.relationship import Relationship
from ...rim.enums import EntityType, RelationshipType
from ...rim.identity import generate_entity_id, generate_relationship_id

import ast
from typing import Dict, List, Optional
from .base import BaseAnalyzer
from ..parser.providers.base import ParsedFile
from ...rim.repository import RepositoryModel
from ...rim.relationship import Relationship
from ...rim.enums import EntityType, RelationshipType
from ...rim.identity import generate_entity_id, generate_relationship_id

class PythonImportVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, repo_id: str = ""):
        self.file_path = file_path
        self.repo_id = repo_id
        self.relationships: List[Relationship] = []
        self.file_id = generate_entity_id(EntityType.FILE, self.file_path, self.file_path, repo_id=self.repo_id)

    def _resolve_module_path(self, module_name: str, level: int = 0) -> str:
        if level > 0:
            parts = self.file_path.split("/")[:-level]
            if module_name:
                parts.append(module_name.replace(".", "/"))
            return "/".join(parts) + ".py"
        return module_name.replace(".", "/") + ".py"

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            mod_id = generate_entity_id(EntityType.MODULE, self.file_path, alias.name, repo_id=self.repo_id)
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
            mod_id = generate_entity_id(EntityType.MODULE, self.file_path, node.module, repo_id=self.repo_id)
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
    supported_languages = ["Python", "TypeScript", "JavaScript", "Java"]

    def __init__(self, repo_id: str = "", file_path: str = ""):
        self.repo_id = repo_id
        self.file_path = file_path

    def analyze(self, repository: RepositoryModel, asts: Dict[str, ParsedFile]) -> None:
        for file_path, parsed in asts.items():
            if parsed.language not in self.supported_languages or not parsed.ast:
                continue

            if parsed.language == "Python":
                visitor = PythonImportVisitor(file_path, repo_id=self.repo_id)
                visitor.visit(parsed.ast)
                for rel in visitor.relationships:
                    self._ensure_target(repository, rel, parsed.language)
                    repository.relationships[rel.id] = rel
            else:
                ast_data = parsed.ast
                if not isinstance(ast_data, dict):
                    continue
                file_id = generate_entity_id(EntityType.FILE, file_path, file_path, repo_id=self.repo_id)
                for imp in ast_data.get("imports", []):
                    module = imp.get("module", "")
                    if not module:
                        continue
                    mod_id = generate_entity_id(EntityType.MODULE, file_path, module, repo_id=self.repo_id)
                    rel = Relationship(
                        id=generate_relationship_id(RelationshipType.IMPORTS, file_id, mod_id),
                        type=RelationshipType.IMPORTS,
                        source_id=file_id,
                        target_id=mod_id,
                        metadata={"module": module}
                    )
                    self._ensure_target(repository, rel, parsed.language)
                    repository.relationships[rel.id] = rel

    def _ensure_target(self, repository: RepositoryModel, rel: Relationship, language: str):
        if rel.target_id not in repository.entities:
            from ...rim.entity import Entity
            from ...rim.location import SourceLocation
            repository.entities[rel.target_id] = Entity(
                id=rel.target_id,
                type=EntityType.MODULE,
                name=rel.metadata.get("module", "unknown"),
                location=SourceLocation(repository_path="external", start_line=1, end_line=1, language=language)
            )

