import ast
from typing import Dict, List
from .base import BaseAnalyzer
from ..parser.providers.base import ParsedFile
from ...rim.repository import RepositoryModel
from ...rim.relationship import Relationship
from ...rim.enums import EntityType, RelationshipType
from ...rim.identity import generate_entity_id, generate_relationship_id

class PythonTypeVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.relationships: List[Relationship] = []
        self.namespace_stack: List[str] = []
        
    def _get_qualified_name(self, name: str) -> str:
        parts = []
        module_path = self.file_path.replace("/", ".").replace(".py", "")
        if module_path.endswith(".__init__"):
            module_path = module_path[:-9]
        if module_path:
            parts.append(module_path)
        parts.extend(self.namespace_stack)
        parts.append(name)
        return ".".join(parts)

    def visit_ClassDef(self, node: ast.ClassDef):
        class_qname = self._get_qualified_name(node.name)
        class_id = generate_entity_id(EntityType.CLASS, self.file_path, class_qname)
        
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_name = base.id
                # Heuristically assume the base is in the same file or a known import
                # A true type resolver would find where `base_name` was imported from.
                base_id = generate_entity_id(EntityType.CLASS, self.file_path, base_name)
                
                rel = Relationship(
                    id=generate_relationship_id(RelationshipType.INHERITS, class_id, base_id),
                    type=RelationshipType.INHERITS,
                    source_id=class_id,
                    target_id=base_id,
                    metadata={"base": base_name}
                )
                self.relationships.append(rel)
                
        self.namespace_stack.append(node.name)
        self.generic_visit(node)
        self.namespace_stack.pop()

class TypeAnalyzer(BaseAnalyzer):
    name = "TypeAnalyzer"
    supported_languages = ["Python"]

    def analyze(self, repository: RepositoryModel, asts: Dict[str, ParsedFile]) -> None:
        for file_path, parsed in asts.items():
            if parsed.language not in self.supported_languages or not parsed.ast:
                continue
                
            visitor = PythonTypeVisitor(file_path)
            visitor.visit(parsed.ast)
            
            for rel in visitor.relationships:
                # We do not create dummy class entities here because we don't know where they live
                # if they are external. If they are local, SymbolAnalyzer should have created them.
                repository.relationships[rel.id] = rel
