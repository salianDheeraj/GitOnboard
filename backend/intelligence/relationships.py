from pathlib import Path
from backend.intelligence.repository_model import RepositoryModel
from backend.intelligence.parser import LanguageParser
class RelationshipBuilder:
    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        self.parser = LanguageParser()
        
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
            ext = file_node.extension.lower()
            if not self.parser.supports_extension(ext):
                continue
                
            pf = self.target_dir / file_node.path
            try:
                with open(pf, "r", encoding="utf-8") as f:
                    source = f.read()
                tree, _ = self.parser.parse_source(source, ext)
                
                # Extract calls
                calls = self.parser.extract_calls(tree, source)
                
                # Determine module id
                parts = list(pf.relative_to(self.target_dir).parts)
                if ext == ".py":
                    if parts[-1] == "__init__.py":
                        parts = parts[:-1]
                    else:
                        parts[-1] = parts[-1][:-3]
                else:
                    parts[-1] = parts[-1].rsplit(".", 1)[0]
                module_id = ".".join(parts) if parts else ""
                
                for caller, callee in calls:
                    caller_id = f"{module_id}::{caller}" if module_id else f"{file_id}::{caller}"
                    if callee in name_to_ids:
                        callee_ids = name_to_ids[callee]
                        if len(callee_ids) == 1:
                            model.relationships.calls.setdefault(caller_id, []).append(callee_ids[0])
                        else:
                            prefix = f"{module_id}::" if module_id else f"{file_id}::"
                            for callee_id in callee_ids:
                                if callee_id.startswith(prefix):
                                    model.relationships.calls.setdefault(caller_id, []).append(callee_id)
                
            except Exception as e:
                pass
                
        # Deduplicate relationships
        for k in model.relationships.contains:
            model.relationships.contains[k] = list(set(model.relationships.contains[k]))
        for k in model.relationships.calls:
            model.relationships.calls[k] = list(set(model.relationships.calls[k]))
        for k in model.relationships.depends_on:
            model.relationships.depends_on[k] = list(set(model.relationships.depends_on[k]))
