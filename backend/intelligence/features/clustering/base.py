from typing import List, Dict, Set
from abc import ABC, abstractmethod

class ClusteringAlgorithm(ABC):
    @abstractmethod
    def cluster(self, weighted_graph: Dict[str, Dict[str, float]]) -> List[List[str]]:
        """
        Clusters the capability IDs based on the weighted graph.
        Returns a list of clusters, where each cluster is a list of capability IDs.
        """
        pass
