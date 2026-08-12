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

class PythonTestVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, repo_id: str = ""):
        self.file_path = file_path
        self.repo_id = repo_id
        self.entities: List[Entity] = []
        self.relationships: List[Relationship] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name.startswith("test_"):
            test_id = generate_entity_id(EntityType.TEST_CASE, self.file_path, node.name, repo_id=self.repo_id)
            
            self.entities.append(Entity(
                id=test_id,
                type=EntityType.TEST_CASE,
                name=node.name,
                location=SourceLocation(repository_path=self.file_path, start_line=node.lineno, end_line=node.lineno, language="Python"),
                metadata={}
            ))
            
        self.generic_visit(node)

class TestAnalyzer(BaseAnalyzer):
    name = "TestAnalyzer"
    supported_languages = ["Python"]

    def __init__(self, repo_id: str = "", file_path: str = ""):
        self.repo_id = repo_id
        self.file_path = file_path

    def analyze(self, repository: RepositoryModel, asts: Dict[str, ParsedFile]) -> None:
        for file_path, parsed in asts.items():
            if parsed.language not in self.supported_languages or not parsed.ast:
                continue
                
            visitor = PythonTestVisitor(file_path, repo_id=self.repo_id)
            visitor.visit(parsed.ast)
            
            for ent in visitor.entities:
                repository.entities[ent.id] = ent
            for rel in visitor.relationships:
                repository.relationships[rel.id] = rel

