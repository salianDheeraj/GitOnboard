from abc import ABC, abstractmethod
from typing import Set, Dict, List
from ...rim.repository import RepositoryModel

class VirtualView(ABC):
    """
    A projected graph tailored for specific analyses.
    """
    def __init__(self, model: RepositoryModel):
        self.model = model
        self.nodes: Set[str] = set()
        self.edges: Dict[str, List[str]] = {}
        self.reverse_edges: Dict[str, List[str]] = {}
        self._build()
        
    @abstractmethod
    def _build(self):
        pass
        
    def add_edge(self, source: str, target: str):
        self.nodes.add(source)
        self.nodes.add(target)
        
        if source not in self.edges:
            self.edges[source] = []
        self.edges[source].append(target)
        
        if target not in self.reverse_edges:
            self.reverse_edges[target] = []
        self.reverse_edges[target].append(source)
        
    def get_neighbors(self, node: str) -> List[str]:
        return self.edges.get(node, [])
        
    def get_reverse_neighbors(self, node: str) -> List[str]:
        return self.reverse_edges.get(node, [])
