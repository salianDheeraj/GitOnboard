"""
Symbol Analyzer: extracts entities (classes, functions, files, directories) from all supported languages.
Works with both Python ASTs (via ast.NodeVisitor) and synthetic ASTs from TS/JS/Java providers.
"""
import ast
from pathlib import Path
from typing import Dict, List
from .base import BaseAnalyzer
from ..parser.providers.base import ParsedFile
from ...rim.repository import RepositoryModel
from ...rim.entity import Entity
from ...rim.relationship import Relationship
from ...rim.enums import EntityType, RelationshipType
from ...rim.location import SourceLocation
from ...rim.identity import generate_entity_id, generate_relationship_id


# --------------------------------------------------------------------------- #
# Python AST visitor
# --------------------------------------------------------------------------- #

class PythonSymbolVisitor(ast.NodeVisitor):
    def __init__(self, file_path: str, source: str, repo_id: str = ""):
        self.file_path = file_path
        self.source_lines = source.splitlines()
        self.repo_id = repo_id
        self.entities: List[Entity] = []
        self.relationships: List[Relationship] = []
        self.namespace_stack: List[tuple] = []
        self.file_id = generate_entity_id(EntityType.FILE, self.file_path, self.file_path, repo_id=self.repo_id)

    def _get_qualified_name(self, name: str) -> str:
        parts = []
        module_path = self.file_path.replace("/", ".").replace(".py", "")
        if module_path.endswith(".__init__"):
            module_path = module_path[:-9]
        if module_path:
            parts.append(module_path)
        parts.extend(ns_name for ns_name, _ in self.namespace_stack)
        if name:
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
        ent_id = generate_entity_id(entity_type, self.file_path, qname, repo_id=self.repo_id)

        if self.namespace_stack:
            parent_qname = self._get_qualified_name("")
            _, parent_type = self.namespace_stack[-1]
            parent_id = generate_entity_id(parent_type, self.file_path, parent_qname, repo_id=self.repo_id)
        else:
            parent_id = self.file_id

        entity = Entity(
            id=ent_id,
            type=entity_type,
            name=name,
            qualified_name=qname,
            display_name=f"{name}()" if entity_type in (EntityType.FUNCTION, EntityType.METHOD) else name,
            location=self._create_location(node),
            metadata={"file_id": self.file_path}
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
        self.namespace_stack.append((node.name, EntityType.CLASS))
        self.generic_visit(node)
        self.namespace_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self.namespace_stack and self.namespace_stack[-1][1] == EntityType.CLASS:
            entity_type = EntityType.METHOD
        else:
            entity_type = EntityType.FUNCTION
        self._add_entity_and_rel(node, node.name, entity_type)
        self.namespace_stack.append((node.name, entity_type))
        self.generic_visit(node)
        self.namespace_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)


# --------------------------------------------------------------------------- #
# Generic provider for TS / JS / Java synthetic ASTs
# --------------------------------------------------------------------------- #

def _process_synthetic_ast(
    file_path: str,
    parsed: ParsedFile,
    repository: RepositoryModel,
    file_id: str,
    repo_id: str = "",
):
    """Process a synthetic AST dict (TypeScript/JavaScript/Java) and populate the RIM."""
    ast_data = parsed.ast  # dict produced by TypeScript/Java provider
    if not isinstance(ast_data, dict):
        return

    language = parsed.language
    symbols = ast_data.get("symbols", [])

    # Map from synthetic type → EntityType
    type_map = {
        "class": EntityType.CLASS,
        "interface": EntityType.CLASS,  # treat interfaces like classes
        "function": EntityType.FUNCTION,
        "type_alias": EntityType.CLASS,  # treat type aliases as nominal symbols
        "enum": EntityType.CLASS,
    }

    for sym in symbols:
        name = sym.get("name", "")
        sym_type_str = sym.get("type", "function")
        entity_type = type_map.get(sym_type_str, EntityType.FUNCTION)
        line = sym.get("line", 1)

        # Qualified name = file_module.SymbolName
        module_path = file_path.rsplit(".", 1)[0].replace("/", ".")
        qname = f"{module_path}.{name}"

        ent_id = generate_entity_id(entity_type, file_path, qname, repo_id=repo_id)
        if ent_id in repository.entities:
            continue

        entity = Entity(
            id=ent_id,
            type=entity_type,
            name=name,
            qualified_name=qname,
            display_name=f"{name}()" if entity_type in (EntityType.FUNCTION, EntityType.METHOD) else name,
            location=SourceLocation(
                repository_path=file_path,
                start_line=line,
                end_line=line,
                language=language
            ),
            metadata={"file_id": file_path}
        )
        repository.entities[ent_id] = entity

        # DECLARES relationship: file → symbol
        rel = Relationship(
            id=generate_relationship_id(RelationshipType.DECLARES, file_id, ent_id),
            type=RelationshipType.DECLARES,
            source_id=file_id,
            target_id=ent_id
        )
        repository.relationships[rel.id] = rel


# --------------------------------------------------------------------------- #
# SymbolAnalyzer
# --------------------------------------------------------------------------- #

from backend.intelligence.rim.identity import generate_stable_id

class SymbolAnalyzer(BaseAnalyzer):
    name = "SymbolAnalyzer"
    supported_languages = ["Python", "TypeScript", "JavaScript", "Java"]

    def __init__(self, repo_id: str = "", file_path: str = ""):
        self.repo_id = repo_id
        self.file_path = file_path

    def analyze(self, repository: RepositoryModel, asts: Dict[str, ParsedFile]) -> None:
        for file_path, parsed in asts.items():
            if parsed.language not in self.supported_languages:
                continue

            # Ensure FILE entity
            file_id = generate_entity_id(EntityType.FILE, file_path, file_path, repo_id=self.repo_id)
            if file_id not in repository.entities:
                repository.entities[file_id] = Entity(
                    id=file_id,
                    type=EntityType.FILE,
                    name=Path(file_path).name,
                    qualified_name=file_path,
                    location=SourceLocation(
                        repository_path=file_path,
                        start_line=1,
                        end_line=max(1, len(parsed.source.splitlines())),
                        language=parsed.language
                    ),
                    metadata={"size": len(parsed.source), "is_supported": True}
                )

            # Ensure DIRECTORY entities
            dir_path = str(Path(file_path).parent).replace("\\", "/")
            if dir_path and dir_path != ".":
                dir_id = generate_entity_id(EntityType.DIRECTORY, dir_path, dir_path, repo_id=self.repo_id)
                if dir_id not in repository.entities:
                    repository.entities[dir_id] = Entity(
                        id=dir_id,
                        type=EntityType.DIRECTORY,
                        name=Path(dir_path).name,
                        qualified_name=dir_path,
                        location=SourceLocation(
                            repository_path=dir_path,
                            start_line=1,
                            end_line=1,
                            language=""
                        ),
                        metadata={}
                    )

            if parsed.language == "Python" and parsed.ast is not None:
                visitor = PythonSymbolVisitor(file_path, parsed.source, repo_id=self.repo_id)
                visitor.visit(parsed.ast)
                for ent in visitor.entities:
                    ent.metadata["file_id"] = file_path
                    repository.entities[ent.id] = ent
                for rel in visitor.relationships:
                    repository.relationships[rel.id] = rel
            else:
                _process_synthetic_ast(file_path, parsed, repository, file_id, repo_id=self.repo_id)

    def extract_symbols(self, asts) -> list[dict]:
        symbols = []
        if isinstance(asts, dict):
            for file_path, parsed in asts.items():
                if parsed.language == "Python" and parsed.ast:
                    visitor = PythonSymbolVisitor(file_path, parsed.source, repo_id=self.repo_id)
                    visitor.visit(parsed.ast)
                    for ent in visitor.entities:
                        sig_hash = ent.metadata.get("signature_hash", "")
                        stable_id = generate_stable_id(self.repo_id, file_path, ent.qualified_name, sig_hash)
                        symbols.append({
                            "stable_id": stable_id,
                            "file_id": f"{self.repo_id}:{file_path}",
                            "name": ent.name,
                            "qualified_name": ent.qualified_name,
                            "symbol_type": ent.type.value.lower() if hasattr(ent.type, "value") else str(ent.type),
                            "line_start": ent.location.start_line,
                            "line_end": ent.location.end_line,
                            "signature_hash": sig_hash,
                            "metadata": ent.metadata
                        })
                elif parsed.ast and isinstance(parsed.ast, dict):
                    for sym in parsed.ast.get("symbols", []):
                        name = sym.get("name", "")
                        sym_type_str = sym.get("type", "function")
                        module_path = file_path.rsplit(".", 1)[0].replace("/", ".")
                        qname = f"{module_path}.{name}"
                        stable_id = generate_stable_id(self.repo_id, file_path, qname, "")
                        symbols.append({
                            "stable_id": stable_id,
                            "file_id": f"{self.repo_id}:{file_path}",
                            "name": name,
                            "qualified_name": qname,
                            "symbol_type": sym_type_str,
                            "line_start": sym.get("line", 1),
                            "line_end": sym.get("line", 1),
                            "signature_hash": "",
                            "metadata": {}
                        })
        return symbols