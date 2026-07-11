import os
import ast
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from .repository_model import (
    RepositoryModel, RepositoryMetadata, RepositoryEntities,
    FileNode, DirectoryNode, ModuleNode, ClassNode, FunctionNode,
    MethodNode, VariableNode, ImportNode
)

def generate_fingerprint(target_dir: Path) -> str:
    # A simple fingerprint using modified time of the top directory or just a static one for MVP
    # In a real scenario, this could be a hash of all file mtimes or commit hash.
    try:
        return str(target_dir.stat().st_mtime)
    except Exception:
        return str(uuid.uuid4())

class RepositoryBuilder:
    """Pure entity ingestion layer. Scans directory and parses AST exactly once."""
    
    def __init__(self, repo_name: str, target_dir: Path):
        self.repo_name = repo_name
        self.target_dir = target_dir
        self.ignored_dirs = {".git", "node_modules", "venv", "build", "dist", "__pycache__"}

    def build(self) -> RepositoryModel:
        metadata = RepositoryMetadata(
            repository_name=self.repo_name,
            repository_path=str(self.target_dir),
            analysis_timestamp=datetime.now(timezone.utc).isoformat(),
            repository_fingerprint=generate_fingerprint(self.target_dir)
        )
        
        entities = RepositoryEntities()
        
        for root, dirs, files in os.walk(self.target_dir):
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            
            rel_root = str(Path(root).relative_to(self.target_dir)).replace("\\", "/")
            if rel_root != ".":
                dir_id = rel_root
                entities.directories[dir_id] = DirectoryNode(
                    id=dir_id,
                    path=rel_root,
                    name=Path(root).name
                )
            
            for file in files:
                if file.startswith("."):
                    continue
                
                pf = Path(root) / file
                rel_path = str(pf.relative_to(self.target_dir)).replace("\\", "/")
                file_id = rel_path
                
                try:
                    size = pf.stat().st_size
                except Exception:
                    size = 0
                
                ext = pf.suffix.lower()
                is_python = ext == ".py"
                
                entities.files[file_id] = FileNode(
                    id=file_id,
                    path=rel_path,
                    name=file,
                    extension=ext,
                    size=size,
                    is_python=is_python
                )
                
                if is_python:
                    self._parse_python_file(pf, file_id, entities)
                    
        return RepositoryModel(metadata=metadata, entities=entities)

    def _parse_python_file(self, pf: Path, file_id: str, entities: RepositoryEntities):
        # Determine module id
        parts = list(pf.relative_to(self.target_dir).parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1][:-3]
            
        module_name = ".".join(parts) if parts else ""
        module_id = module_name
        
        if module_id and module_id not in entities.modules:
            entities.modules[module_id] = ModuleNode(
                id=module_id,
                name=module_name,
                file_id=file_id
            )
            
        try:
            with open(pf, "r", encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source)
            
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imp_id = f"{file_id}::import::{alias.name}"
                        entities.imports[imp_id] = ImportNode(
                            id=imp_id,
                            file_id=file_id,
                            module_name=alias.name,
                            alias=alias.asname
                        )
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for alias in node.names:
                        imported_name = f"{mod}.{alias.name}" if mod else alias.name
                        imp_id = f"{file_id}::import::{imported_name}"
                        entities.imports[imp_id] = ImportNode(
                            id=imp_id,
                            file_id=file_id,
                            module_name=imported_name,
                            alias=alias.asname
                        )
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fn_id = f"{module_id}::{node.name}" if module_id else f"{file_id}::{node.name}"
                    params = [arg.arg for arg in node.args.args] if hasattr(node, "args") else []
                    entities.functions[fn_id] = FunctionNode(
                        id=fn_id,
                        name=node.name,
                        file_id=file_id,
                        module_id=module_id,
                        line_number=getattr(node, "lineno", 0),
                        docstring=ast.get_docstring(node) or "",
                        parameters=params,
                        is_async=isinstance(node, ast.AsyncFunctionDef)
                    )
                elif isinstance(node, ast.ClassDef):
                    cls_id = f"{module_id}::{node.name}" if module_id else f"{file_id}::{node.name}"
                    entities.classes[cls_id] = ClassNode(
                        id=cls_id,
                        name=node.name,
                        file_id=file_id,
                        module_id=module_id,
                        line_number=getattr(node, "lineno", 0),
                        docstring=ast.get_docstring(node) or ""
                    )
                    for class_node in node.body:
                        if isinstance(class_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            method_id = f"{cls_id}.{class_node.name}"
                            params = [arg.arg for arg in class_node.args.args] if hasattr(class_node, "args") else []
                            entities.methods[method_id] = MethodNode(
                                id=method_id,
                                name=class_node.name,
                                class_id=cls_id,
                                file_id=file_id,
                                module_id=module_id,
                                line_number=getattr(class_node, "lineno", 0),
                                docstring=ast.get_docstring(class_node) or "",
                                parameters=params,
                                is_async=isinstance(class_node, ast.AsyncFunctionDef)
                            )
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            var_id = f"{module_id}::{target.id}" if module_id else f"{file_id}::{target.id}"
                            entities.variables[var_id] = VariableNode(
                                id=var_id,
                                name=target.id,
                                file_id=file_id,
                                line_number=getattr(node, "lineno", 0)
                            )
        except Exception as e:
            pass
