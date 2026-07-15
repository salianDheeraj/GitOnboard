from abc import ABC, abstractmethod
from ..model.intelligence import Intelligence, IntelligenceType
from ..core.context import ProviderContext

class IntelligenceProvider(ABC):
    @property
    @abstractmethod
    def type(self) -> IntelligenceType:
        pass
        
    @abstractmethod
    def run(self, context: ProviderContext) -> Intelligence:
        pass
