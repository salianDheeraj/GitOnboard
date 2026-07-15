from typing import List, Dict
from ..providers.base import IntelligenceProvider
from ..model.intelligence import IntelligenceType

class IntelligenceRegistry:
    def __init__(self):
        self._providers: Dict[IntelligenceType, IntelligenceProvider] = {}
        
    def register(self, provider: IntelligenceProvider):
        self._providers[provider.type] = provider
        
    def get_providers(self, types: List[IntelligenceType] = None) -> List[IntelligenceProvider]:
        if not types:
            return list(self._providers.values())
        return [self._providers[t] for t in types if t in self._providers]
