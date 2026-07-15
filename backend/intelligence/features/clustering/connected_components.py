from typing import List, Dict, Set
from .base import ClusteringAlgorithm

class ConnectedComponents(ClusteringAlgorithm):
    def __init__(self, threshold: float = 0.65):
        self.threshold = threshold
        
    def cluster(self, weighted_graph: Dict[str, Dict[str, float]]) -> List[List[str]]:
        visited: Set[str] = set()
        clusters: List[List[str]] = []
        
        for node in weighted_graph.keys():
            if node not in visited:
                cluster = self._bfs(node, weighted_graph, visited)
                if cluster:
                    clusters.append(cluster)
                    
        return clusters
        
    def _bfs(self, start_node: str, graph: Dict[str, Dict[str, float]], visited: Set[str]) -> List[str]:
        queue = [start_node]
        cluster = []
        
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                cluster.append(curr)
                
                # Check neighbors
                for neighbor, weight in graph.get(curr, {}).items():
                    if neighbor not in visited and weight >= self.threshold:
                        queue.append(neighbor)
                        
        return cluster
