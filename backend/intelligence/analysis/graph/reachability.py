from typing import Set, List
from ..composer.views.base import VirtualView
from .bfs import BFS

class Reachability:
    @staticmethod
    def forward(view: VirtualView, start_node: str) -> Set[str]:
        return BFS.traverse(view, start_node)
        
    @staticmethod
    def reverse(view: VirtualView, end_node: str) -> Set[str]:
        visited = set()
        queue = [end_node]
        
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                for neighbor in view.get_reverse_neighbors(curr):
                    if neighbor not in visited:
                        queue.append(neighbor)
                        
        return visited

class NeighborhoodSearch:
    @staticmethod
    def find_neighborhood(view: VirtualView, start_node: str, radius: int = 1) -> Set[str]:
        visited = {start_node}
        queue = [(start_node, 0)]
        
        while queue:
            curr, depth = queue.pop(0)
            
            if depth < radius:
                for neighbor in view.get_neighbors(curr):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))
                        
                for neighbor in view.get_reverse_neighbors(curr):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))
                        
        return visited
