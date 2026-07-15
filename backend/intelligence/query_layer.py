from typing import List, Dict, Optional, Any
from .rim.repository import RepositoryModel
from .rim.entity import Entity
from .rim.enums import EntityType

class QueryLayer:
    """Unified interface for accessing the RepositoryModel using Entity Indexes."""

    def __init__(self, model: RepositoryModel):
        self.model = model
        self._build_indexes()

    def _build_indexes(self):
        # Function Name -> List of Function IDs
        self._func_name_idx: Dict[str, List[str]] = {}
        # Class Name -> List of Class IDs
        self._class_name_idx: Dict[str, List[str]] = {}
        # File -> Classes
        self._file_to_classes_idx: Dict[str, List[str]] = {}
        # Module -> Functions
        self._module_to_functions_idx: Dict[str, List[str]] = {}

        for eid, entity in self.model.entities.items():
            if entity.type == EntityType.FUNCTION:
                self._func_name_idx.setdefault(entity.name, []).append(eid)
                # metadata might store module_id, or we can use location.repository_path
                module_id = entity.metadata.get("module_id", entity.location.repository_path)
                self._module_to_functions_idx.setdefault(module_id, []).append(eid)
            elif entity.type == EntityType.CLASS:
                self._class_name_idx.setdefault(entity.name, []).append(eid)
                # file_id could be location.repository_path
                file_id = entity.metadata.get("file_id", entity.location.repository_path)
                self._file_to_classes_idx.setdefault(file_id, []).append(eid)

    def find_function(self, name: str) -> List[Entity]:
        ids = self._func_name_idx.get(name, [])
        return [self.model.entities[eid] for eid in ids if eid in self.model.entities]

    def get_class(self, name: str) -> List[Entity]:
        ids = self._class_name_idx.get(name, [])
        return [self.model.entities[eid] for eid in ids if eid in self.model.entities]

    def get_file(self, file_id: str) -> Optional[Entity]:
        return self.model.entities.get(file_id)

    def get_dependencies(self, file_id: str) -> List[str]:
        # Filter relationships where type = DEPENDS_ON and source_id = file_id
        return [r.target_id for r in self.model.relationships.values() if r.type == "DEPENDS_ON" and r.source_id == file_id]

    def get_calls(self, function_id: str) -> List[str]:
        return [r.target_id for r in self.model.relationships.values() if r.type == "CALLS" and r.source_id == function_id]

    def get_classes_in_file(self, file_id: str) -> List[Entity]:
        ids = self._file_to_classes_idx.get(file_id, [])
        return [self.model.entities[eid] for eid in ids if eid in self.model.entities]

    def get_functions_in_module(self, module_id: str) -> List[Entity]:
        ids = self._module_to_functions_idx.get(module_id, [])
        return [self.model.entities[eid] for eid in ids if eid in self.model.entities]

    def get_directories(self) -> List[Entity]:
        return [e for e in self.model.entities.values() if e.type == EntityType.DIRECTORY]

    def get_files(self) -> List[Entity]:
        return [e for e in self.model.entities.values() if e.type == EntityType.FILE]

    def search_entities(self, query: str) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        results = []
        for fn_name, fn_ids in self._func_name_idx.items():
            if query_lower in fn_name.lower():
                for eid in fn_ids:
                    fn = self.model.entities[eid]
                    results.append({"type": "function", "name": fn.name, "id": eid, "file": fn.location.repository_path})
        
        for cls_name, cls_ids in self._class_name_idx.items():
            if query_lower in cls_name.lower():
                for eid in cls_ids:
                    cls = self.model.entities[eid]
                    results.append({"type": "class", "name": cls.name, "id": eid, "file": cls.location.repository_path})
                    
        return results
