import ast
from typing import Dict, List
from .base import BaseAnalyzer
from ..parser.providers.base import ParsedFile
from ...rim.repository import RepositoryModel
from ...rim.entity import Entity
from ...rim.relationship import Relationship
from ...rim.enums import EntityType, RelationshipType
from ...rim.location import SourceLocation
from ...rim.identity import generate_entity_id, generate_relationship_id, generate_stable_id

class PythonRouteVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, repo_id: str = ""):
        self.file_path = file_path
        self.repo_id = repo_id
        self.entities: List[Entity] = []
        self.relationships: List[Relationship] = []

    def _get_qualified_name(self, name: str) -> str:
        parts = []
        module_path = self.file_path.replace("/", ".").replace(".py", "")
        if module_path.endswith(".__init__"):
            module_path = module_path[:-9]
        if module_path:
            parts.append(module_path)
        if name:
            parts.append(name)
        return ".".join(parts)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                func = decorator.func
                method = None
                
                # Check for @app.get(), @router.post(), etc.
                if isinstance(func, ast.Attribute) and func.attr in ("get", "post", "put", "delete", "patch"):
                    method = func.attr.upper()
                
                if method and decorator.args:
                    arg = decorator.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        path = arg.value
                        
                        route_name = f"{method} {path}"
                        route_id = generate_stable_id(self.repo_id, self.file_path, f"route:{method}:{path}", "")
                        
                        self.entities.append(Entity(
                            id=route_id,
                            type=EntityType.ROUTE,
                            name=route_name,
                            location=SourceLocation(
                                repository_path=self.file_path,
                                start_line=node.lineno,
                                end_line=node.lineno,
                                language="Python"
                            ),
                            metadata={"method": method, "path": path, "framework": "FastAPI/Flask"}
                        ))
                        
                        func_qname = self._get_qualified_name(node.name)
                        func_id = generate_stable_id(self.repo_id, self.file_path, func_qname, "")
                        
                        self.relationships.append(Relationship(
                            id=generate_relationship_id(RelationshipType.EXPOSES, func_id, route_id),
                            type=RelationshipType.EXPOSES,
                            source_id=func_id,
                            target_id=route_id
                        ))
                        
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)


class RouteAnalyzer(BaseAnalyzer):
    name = "RouteAnalyzer"
    supported_languages = ["Python"]

    def __init__(self, repo_id: str = "", file_path: str = ""):
        self.repo_id = repo_id
        self.file_path = file_path

    def analyze(self, repository: RepositoryModel, asts: Dict[str, ParsedFile]) -> None:
        for file_path, parsed in asts.items():
            if parsed.language not in self.supported_languages or not parsed.ast:
                continue
            visitor = PythonRouteVisitor(file_path, repo_id=self.repo_id)
            visitor.visit(parsed.ast)
            for ent in visitor.entities:
                repository.entities[ent.id] = ent
            for rel in visitor.relationships:
                repository.relationships[rel.id] = rel

    def extract_routes(self, asts, symbols: list[dict] = None) -> list[dict]:
        routes = []
        symbol_map = {}
        if symbols:
            for s in symbols:
                file_p = s.get("file_id", "").split(":", 1)[-1]
                symbol_map[(file_p, s.get("qualified_name"))] = s.get("stable_id")
                symbol_map[(file_p, s.get("name"))] = s.get("stable_id")

        if isinstance(asts, dict):
            for file_path, parsed in asts.items():
                if parsed.language == "Python" and parsed.ast:
                    visitor = PythonRouteVisitor(file_path, repo_id=self.repo_id)
                    visitor.visit(parsed.ast)
                    for ent in visitor.entities:
                        if ent.type == EntityType.ROUTE:
                            method = ent.metadata.get("method", "GET")
                            path = ent.metadata.get("path", "/")
                            handler_symbol_id = ""
                            for rel in visitor.relationships:
                                if rel.target_id == ent.id and rel.type == RelationshipType.EXPOSES:
                                    handler_symbol_id = rel.source_id
                                    break
                            
                            # If symbols dict provides a direct match for this handler, prefer symbol_map
                            func_name = ent.name.split()[-1] if " " in ent.name else ""
                            matched_id = symbol_map.get((file_path, func_name)) or symbol_map.get((file_path, handler_symbol_id))
                            if matched_id:
                                handler_symbol_id = matched_id

                            route_id = generate_stable_id(self.repo_id, file_path, f"route:{method}:{path}", "")
                            routes.append({
                                "id": route_id,
                                "symbol_id": route_id,
                                "method": method,
                                "path": path,
                                "handler_symbol_id": handler_symbol_id
                            })
        return routes

