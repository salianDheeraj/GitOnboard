from abc import ABC, abstractmethod
from typing import Dict, Any, List

class IntelligenceStore(ABC):
    """
    The canonical persistence layer for all Repository Intelligence artifacts.
    """
    
    @abstractmethod
    def save_repository_model(self, model_data: Dict[str, Any]):
        pass
        
    @abstractmethod
    def save_derived_model(self, model_type: str, data: Any):
        pass
        
    @abstractmethod
    def save_intelligence(self, intelligence: Any):
        pass

class MemoryStore(IntelligenceStore):
    def __init__(self):
        self.repository_model = None
        self.derived_models = {}
        self.intelligence = []
        
    def save_repository_model(self, model_data: Dict[str, Any]):
        self.repository_model = model_data
        
    def save_derived_model(self, model_type: str, data: Any):
        self.derived_models[model_type] = data
        
    def save_intelligence(self, intelligence: Any):
        self.intelligence.append(intelligence)
