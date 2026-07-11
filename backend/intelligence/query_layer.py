from typing import List, Dict, Optional, Any
from .repository_model import RepositoryModel, FunctionNode, ClassNode, FileNode, DirectoryNode, MethodNode

class QueryLayer:
    """Unified interface for accessing the RepositoryModel using Entity Indexes."""

    def __init__(self, model: RepositoryModel):
        self.model = model
        self._build_indexes()

    def _build_indexes(self):
        # Function Name -> List of Function IDs
        self._func_name_idx: Dict[str, List[str]] = {}
        for fn_id, fn in self.model.entities.functions.items():
            self._func_name_idx.setdefault(fn.name, []).append(fn_id)

        # Class Name -> List of Class IDs
        self._class_name_idx: Dict[str, List[str]] = {}
        for cls_id, cls in self.model.entities.classes.items():
            self._class_name_idx.setdefault(cls.name, []).append(cls_id)

        # File -> Classes
        self._file_to_classes_idx: Dict[str, List[str]] = {}
        for cls_id, cls in self.model.entities.classes.items():
            self._file_to_classes_idx.setdefault(cls.file_id, []).append(cls_id)

        # Module -> Functions
        self._module_to_functions_idx: Dict[str, List[str]] = {}
        for fn_id, fn in self.model.entities.functions.items():
            self._module_to_functions_idx.setdefault(fn.module_id, []).append(fn_id)

    def find_function(self, name: str) -> List[FunctionNode]:
        ids = self._func_name_idx.get(name, [])
        return [self.model.entities.functions[fn_id] for fn_id in ids if fn_id in self.model.entities.functions]

    def get_class(self, name: str) -> List[ClassNode]:
        ids = self._class_name_idx.get(name, [])
        return [self.model.entities.classes[cls_id] for cls_id in ids if cls_id in self.model.entities.classes]

    def get_file(self, file_id: str) -> Optional[FileNode]:
        return self.model.entities.files.get(file_id)

    def get_dependencies(self, file_id: str) -> List[str]:
        return self.model.relationships.depends_on.get(file_id, [])

    def get_calls(self, function_id: str) -> List[str]:
        return self.model.relationships.calls.get(function_id, [])

    def get_classes_in_file(self, file_id: str) -> List[ClassNode]:
        ids = self._file_to_classes_idx.get(file_id, [])
        return [self.model.entities.classes[cls_id] for cls_id in ids if cls_id in self.model.entities.classes]

    def get_functions_in_module(self, module_id: str) -> List[FunctionNode]:
        ids = self._module_to_functions_idx.get(module_id, [])
        return [self.model.entities.functions[fn_id] for fn_id in ids if fn_id in self.model.entities.functions]

    # Useful for architecture
    def get_directories(self) -> List[DirectoryNode]:
        return list(self.model.entities.directories.values())

    def get_files(self) -> List[FileNode]:
        return list(self.model.entities.files.values())

    def search_entities(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        results = []
        # basic search over functions and classes
        for fn_name, fn_ids in self._func_name_idx.items():
            if query_lower in fn_name.lower():
                for fn_id in fn_ids:
                    fn = self.model.entities.functions[fn_id]
                    results.append({"type": "function", "name": fn.name, "id": fn_id, "file": fn.file_id})
        
        for cls_name, cls_ids in self._class_name_idx.items():
            if query_lower in cls_name.lower():
                for cls_id in cls_ids:
                    cls = self.model.entities.classes[cls_id]
                    results.append({"type": "class", "name": cls.name, "id": cls_id, "file": cls.file_id})
                    
        return results
