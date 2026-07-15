from typing import List, Dict, Type
from .base import BaseAnalyzer

class AnalyzerRegistry:
    """
    Holds registered analyzers and resolves dependencies.
    """
    def __init__(self):
        self._analyzers: List[BaseAnalyzer] = []

    def register(self, analyzer: BaseAnalyzer) -> None:
        self._analyzers.append(analyzer)

    def get_all(self) -> List[BaseAnalyzer]:
        return self._analyzers
