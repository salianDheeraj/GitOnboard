from typing import Dict, Type
from ..model.analysis import RepositoryAnalysis

class AnalysisRegistry:
    """
    Central registry for all deterministic analyses.
    """
    def __init__(self):
        self._registry: Dict[str, Type[RepositoryAnalysis]] = {}
        
    def register(self, analysis_class: Type[RepositoryAnalysis]):
        # Instantiate to get the name property
        instance = analysis_class()
        self._registry[instance.name.lower()] = analysis_class
        
    def get(self, name: str) -> Type[RepositoryAnalysis]:
        return self._registry.get(name.lower())
        
    def list_analyses(self) -> Dict[str, str]:
        return {name: cls().description for name, cls in self._registry.items()}
