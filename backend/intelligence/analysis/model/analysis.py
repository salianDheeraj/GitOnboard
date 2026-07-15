from abc import ABC, abstractmethod
from typing import Any, Dict
from ...rim.repository import RepositoryModel
from .result import AnalysisResult

class RepositoryAnalysis(ABC):
    """
    Contract for all deterministic graph analyses.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        pass
        
    @property
    @abstractmethod
    def description(self) -> str:
        pass
        
    @abstractmethod
    def execute(self, repository: RepositoryModel, options: Dict[str, Any] = None) -> AnalysisResult[Any]:
        pass
