import ast
from pathlib import Path
from backend.intelligence.repository_model import RepositoryModel

class RelationshipBuilder:
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        
    def build(self, model: RepositoryModel):
        # Build "contains" (file -> classes/functions)
        for cls_id, cls in model.entities.classes.items():
            model.relationships.contains.setdefault(cls.file_id, []).append(cls_id)
        for fn_id, fn in model.entities.functions.items():
            model.relationships.contains.setdefault(fn.file_id, []).append(fn_id)
            
        # Build a module map
        module_map = {}
        for mod_id, mod in model.entities.modules.items():
            module_map[mod.name] = mod.file_id

        # Extract dependencies from imports
        for imp_id, imp in model.entities.imports.items():
            # Only add dependency if the imported module is internal
            target_module = imp.module_name
            if target_module in module_map:
                model.relationships.depends_on.setdefault(imp.file_id, []).append(module_map[target_module])
            else:
                # E.g. from src.auth import something -> imp.module_name is src.auth.something
                # check if the parent module is in the map
                parts = target_module.split('.')
                for i in range(len(parts), 0, -1):
                    parent_mod = ".".join(parts[:i])
                    if parent_mod in module_map:
                        model.relationships.depends_on.setdefault(imp.file_id, []).append(module_map[parent_mod])
                        break
            
        # We need a quick pass to extract call relationships.
        # Since we want deterministic IDs, we match calls similarly.
        # For a production system this requires deep static analysis.
        # For MVP, we will reuse the ast visitor approach to just find name matches.
        self._build_calls(model)
        
    def _build_calls(self, model: RepositoryModel):
        # Build a reverse lookup for function names to IDs to resolve calls
        name_to_ids = {}
        for fn_id, fn in model.entities.functions.items():
            name_to_ids.setdefault(fn.name, []).append(fn_id)
        for method_id, method in model.entities.methods.items():
            name_to_ids.setdefault(method.name, []).append(method_id)
            
        for file_id, file_node in model.entities.files.items():
            if not file_node.is_python:
                continue
                
            pf = self.target_dir / file_node.path
            try:
                with open(pf, "r", encoding="utf-8") as f:
                    source = f.read()
                tree = ast.parse(source)
                
                # Simple visitor to find calls
                class CallVisitor(ast.NodeVisitor):
                    def __init__(self, module_id, file_id):
                        self.module_id = module_id
                        self.file_id = file_id
                        self.current_caller = None
                        
                    def visit_FunctionDef(self, node):
                        prev = self.current_caller
                        self.current_caller = f"{self.module_id}::{node.name}" if self.module_id else f"{self.file_id}::{node.name}"
                        self.generic_visit(node)
                        self.current_caller = prev
                        
                    def visit_AsyncFunctionDef(self, node):
                        self.visit_FunctionDef(node)
                        
                    def visit_ClassDef(self, node):
                        prev = self.current_caller
                        cls_id = f"{self.module_id}::{node.name}" if self.module_id else f"{self.file_id}::{node.name}"
                        for child in node.body:
                            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                self.current_caller = f"{cls_id}.{child.name}"
                                self.generic_visit(child)
                        self.current_caller = prev
                        
                    def visit_Call(self, node):
                        if self.current_caller:
                            func_name = None
                            if isinstance(node.func, ast.Name):
                                func_name = node.func.id
                            elif isinstance(node.func, ast.Attribute):
                                func_name = node.func.attr
                                
                            if func_name and func_name in name_to_ids:
                                callee_ids = name_to_ids[func_name]
                                if len(callee_ids) == 1:
                                    model.relationships.calls.setdefault(self.current_caller, []).append(callee_ids[0])
                                else:
                                    # Too many matches. Only link if it's in the same module to avoid graph explosion
                                    prefix = f"{self.module_id}::" if self.module_id else f"{self.file_id}::"
                                    for callee_id in callee_ids:
                                        if callee_id.startswith(prefix):
                                            model.relationships.calls.setdefault(self.current_caller, []).append(callee_id)
                        self.generic_visit(node)
                        
                # Determine module id
                parts = list(pf.relative_to(self.target_dir).parts)
                if parts[-1] == "__init__.py":
                    parts = parts[:-1]
                else:
                    parts[-1] = parts[-1][:-3]
                module_id = ".".join(parts) if parts else ""
                
                visitor = CallVisitor(module_id, file_id)
                visitor.visit(tree)
                
            except Exception:
                pass
                
        # Deduplicate relationships
        for k in model.relationships.contains:
            model.relationships.contains[k] = list(set(model.relationships.contains[k]))
        for k in model.relationships.calls:
            model.relationships.calls[k] = list(set(model.relationships.calls[k]))
        for k in model.relationships.depends_on:
            model.relationships.depends_on[k] = list(set(model.relationships.depends_on[k]))
