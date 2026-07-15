import ast
from typing import Dict, List
from .base import BaseAnalyzer
from ..parser.providers.base import ParsedFile
from ...rim.repository import RepositoryModel
from ...rim.entity import Entity
from ...rim.relationship import Relationship
from ...rim.enums import EntityType, RelationshipType
from ...rim.location import SourceLocation
from ...rim.identity import generate_entity_id, generate_relationship_id

class PythonSymbolVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, source: str):
        self.file_path = file_path
        self.source_lines = source.splitlines()
        self.entities: List[Entity] = []
        self.relationships: List[Relationship] = []
        self.namespace_stack: List[str] = []
        
        # File entity ID
        self.file_id = generate_entity_id(EntityType.FILE, self.file_path, self.file_path)

    def _get_qualified_name(self, name: str) -> str:
        parts = []
        # Add module path
        module_path = self.file_path.replace("/", ".").replace(".py", "")
        if module_path.endswith(".__init__"):
            module_path = module_path[:-9]
        if module_path:
            parts.append(module_path)
            
        parts.extend(self.namespace_stack)
        parts.append(name)
        return ".".join(parts)

    def _create_location(self, node: ast.AST) -> SourceLocation:
        return SourceLocation(
            repository_path=self.file_path,
            start_line=getattr(node, "lineno", 1),
            end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
            start_column=getattr(node, "col_offset", 0) + 1,
            end_column=getattr(node, "end_col_offset", getattr(node, "col_offset", 0)) + 1,
            language="Python"
        )

    def _add_entity_and_rel(self, node: ast.AST, name: str, entity_type: EntityType):
        qname = self._get_qualified_name(name)
        ent_id = generate_entity_id(entity_type, self.file_path, qname)
        
        # Determine parent ID (file or parent class/function)
        if self.namespace_stack:
            parent_qname = self._get_qualified_name("")[:-1]
            # Heuristic: if parent is class, it's a CLASS, else FUNCTION (for nested)
            # This is a simplification.
            parent_type = EntityType.CLASS if len(self.namespace_stack) > 0 else EntityType.FILE
            parent_id = generate_entity_id(parent_type, self.file_path, parent_qname)
        else:
            parent_id = self.file_id
            
        entity = Entity(
            id=ent_id,
            type=entity_type,
            name=name,
            qualified_name=qname,
            display_name=f"{name}()" if entity_type in (EntityType.FUNCTION, EntityType.METHOD) else name,
            location=self._create_location(node),
            metadata={}
        )
        self.entities.append(entity)
        
        rel = Relationship(
            id=generate_relationship_id(RelationshipType.DECLARES, parent_id, ent_id),
            type=RelationshipType.DECLARES,
            source_id=parent_id,
            target_id=ent_id
        )
        self.relationships.append(rel)
        return ent_id

    def visit_ClassDef(self, node: ast.ClassDef):
        self._add_entity_and_rel(node, node.name, EntityType.CLASS)
        self.namespace_stack.append(node.name)
        self.generic_visit(node)
        self.namespace_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        entity_type = EntityType.METHOD if self.namespace_stack else EntityType.FUNCTION
        self._add_entity_and_rel(node, node.name, entity_type)
        self.namespace_stack.append(node.name)
        self.generic_visit(node)
        self.namespace_stack.pop()
        
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node) # handle same as sync


class SymbolAnalyzer(BaseAnalyzer):
    name = "SymbolAnalyzer"
    supported_languages = ["Python"]

    def analyze(self, repository: RepositoryModel, asts: Dict[str, ParsedFile]) -> None:
        for file_path, parsed in asts.items():
            if parsed.language not in self.supported_languages or not parsed.ast:
                continue
                
            # Ensure File entity exists
            file_id = generate_entity_id(EntityType.FILE, file_path, file_path)
            if file_id not in repository.entities:
                repository.entities[file_id] = Entity(
                    id=file_id,
                    type=EntityType.FILE,
                    name=file_path.split("/")[-1],
                    qualified_name=file_path,
                    location=SourceLocation(repository_path=file_path, start_line=1, end_line=1, language="Python"),
                    metadata={"size": len(parsed.source)}
                )
                
            visitor = PythonSymbolVisitor(file_path, parsed.source)
            visitor.visit(parsed.ast)
            
            for ent in visitor.entities:
                repository.entities[ent.id] = ent
            for rel in visitor.relationships:
                repository.relationships[rel.id] = rel
