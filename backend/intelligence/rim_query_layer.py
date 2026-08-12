"""
QueryLayer: A simple facade over the RIM RepositoryModel for router-level queries.
"""
from typing import List, Iterator
from backend.intelligence.rim.repository import RepositoryModel
from backend.intelligence.rim.enums import EntityType
from backend.intelligence.rim.entity import Entity


class QueryLayer:
    """
    Wraps a RepositoryModel and exposes convenience methods for routers.
    """

    def __init__(self, model: RepositoryModel):
        self.model = model

    def get_files(self) -> Iterator[Entity]:
        """Yield all FILE entities."""
        for e in self.model.entities.values():
            if e.type == EntityType.FILE:
                yield e

    def get_directories(self) -> Iterator[Entity]:
        """Yield all DIRECTORY entities."""
        for e in self.model.entities.values():
            if e.type == EntityType.DIRECTORY:
                yield e

    def get_classes_in_file(self, file_path: str) -> List[Entity]:
        """Return all CLASS entities that belong to the given file path."""
        return [
            e for e in self.model.entities.values()
            if e.type == EntityType.CLASS
            and (e.metadata.get("file_id") == file_path or e.location.repository_path == file_path)
        ]

    def get_functions_in_module(self, file_path: str) -> List[Entity]:
        """Return all FUNCTION entities that belong to the given file path."""
        return [
            e for e in self.model.entities.values()
            if e.type == EntityType.FUNCTION
            and (e.metadata.get("file_id") == file_path or e.location.repository_path == file_path)
        ]

    def get_file(self, file_path: str):
        """Return the FILE entity for the given repository path, or None."""
        for e in self.model.entities.values():
            if e.type == EntityType.FILE and e.location.repository_path == file_path:
                return e
        return None

    def search_entities(self, query: str) -> List[dict]:
        """Simple case-insensitive name search over functions and classes."""
        q = query.lower()
        results = []
        for e in self.model.entities.values():
            if e.type in (EntityType.FUNCTION, EntityType.CLASS, EntityType.METHOD):
                if q in e.name.lower():
                    results.append({
                        "id": e.id,
                        "name": e.name,
                        "type": e.type.value.lower(),
                        "file": e.metadata.get("file_id", e.location.repository_path),
                    })
        return results[:50]
