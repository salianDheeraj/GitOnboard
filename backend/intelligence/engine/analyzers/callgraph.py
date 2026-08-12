import ast
from typing import Dict, List
from .base import BaseAnalyzer
from ..parser.providers.base import ParsedFile
from ...rim.repository import RepositoryModel
from ...rim.relationship import Relationship
from ...rim.enums import EntityType, RelationshipType
from ...rim.identity import generate_entity_id, generate_relationship_id, generate_stable_id

class PythonCallGraphVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, repo_id: str = "", symbol_map: dict = None):
        self.file_path = file_path
        self.repo_id = repo_id
        self.symbol_map = symbol_map or {}
        self.relationships: List[Relationship] = []
        self.current_caller_id: str = None
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
        self.namespace_stack.append(node.name)
        self.generic_visit(node)
        self.namespace_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        qname = self._get_qualified_name(node.name)
        # Check symbol map first or generate stable ID
        caller_id = self.symbol_map.get((self.file_path, qname)) or self.symbol_map.get((self.file_path, node.name))
        if not caller_id:
            caller_id = generate_stable_id(self.repo_id, self.file_path, qname, "")
        
        prev_caller = self.current_caller_id
        self.current_caller_id = caller_id
        self.namespace_stack.append(node.name)
        
        self.generic_visit(node)
        
        self.namespace_stack.pop()
        self.current_caller_id = prev_caller

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)

    def visit_Call(self, node: ast.Call):
        if self.current_caller_id:
            callee_name = None
            if isinstance(node.func, ast.Name):
                callee_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                callee_name = node.func.attr
                
            if callee_name:
                callee_id = self.symbol_map.get((self.file_path, callee_name))
                if not callee_id:
                    callee_id = self.symbol_map.get(callee_name)
                if not callee_id:
                    callee_qname = self._get_qualified_name(callee_name)
                    callee_id = generate_stable_id(self.repo_id, self.file_path, callee_qname, "")
                
                rel = Relationship(
                    id=generate_relationship_id(RelationshipType.CALLS, self.current_caller_id, callee_id),
                    type=RelationshipType.CALLS,
                    source_id=self.current_caller_id,
                    target_id=callee_id,
                    metadata={"call_name": callee_name}
                )
                self.relationships.append(rel)
                
        self.generic_visit(node)


class CallGraphAnalyzer(BaseAnalyzer):
    name = "CallGraphAnalyzer"
    supported_languages = ["Python"]

    def __init__(self, repo_id: str = "", file_path: str = ""):
        self.repo_id = repo_id
        self.file_path = file_path

    def analyze(self, repository: RepositoryModel, asts: Dict[str, ParsedFile]) -> None:
        for file_path, parsed in asts.items():
            if parsed.language not in self.supported_languages or not parsed.ast:
                continue
                
            visitor = PythonCallGraphVisitor(file_path, repo_id=self.repo_id)
            visitor.visit(parsed.ast)
            
            for rel in visitor.relationships:
                repository.relationships[rel.id] = rel

    def extract_relationships(self, asts, symbols: list[dict] = None) -> list[dict]:
        relationships = []
        symbol_map = {}
        if symbols:
            for s in symbols:
                file_p = s.get("file_id", "").split(":", 1)[-1]
                st_id = s.get("stable_id")
                qname = s.get("qualified_name")
                name = s.get("name")
                if file_p and qname:
                    symbol_map[(file_p, qname)] = st_id
                if file_p and name:
                    symbol_map[(file_p, name)] = st_id
                if name and name not in symbol_map:
                    symbol_map[name] = st_id

        if isinstance(asts, dict):
            for file_path, parsed in asts.items():
                if parsed.language == "Python" and parsed.ast:
                    visitor = PythonCallGraphVisitor(file_path, repo_id=self.repo_id, symbol_map=symbol_map)
                    visitor.visit(parsed.ast)
                    for rel in visitor.relationships:
                        rel_type_str = rel.type.value if hasattr(rel.type, "value") else str(rel.type)
                        relationships.append({
                            "id": rel.id,
                            "from_symbol_id": rel.source_id,
                            "to_symbol_id": rel.target_id,
                            "rel_type": rel_type_str,
                            "evidence_line": None,
                            "evidence_snippet": rel.metadata.get("call_name") if rel.metadata else None,
                            "status": "CONFIRMED"
                        })
        return relationships

