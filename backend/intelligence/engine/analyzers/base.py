from typing import Protocol, List, Dict
from ..parser.providers.base import ParsedFile
from ...rim.repository import RepositoryModel
from ...rim.entity import Entity
from ...rim.relationship import Relationship
from ...rim.enums import EntityType, RelationshipType

class BaseAnalyzer(Protocol):
    """
    Interface for all deterministic static analyzers.
    """
    name: str
    supported_languages: List[str]

    def analyze(self, repository: RepositoryModel, asts: Dict[str, ParsedFile]) -> None:
        """
        Extract facts from the ASTs and populate the repository model with Entities and Relationships.
        Should not mutate existing entities, only add new facts or relationships.
        """
        ...
