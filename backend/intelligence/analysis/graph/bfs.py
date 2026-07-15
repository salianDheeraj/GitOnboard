from typing import List, Set, Callable
from ..composer.views.base import VirtualView
from .traversal import Traversal

class BFS:
    @staticmethod
    def traverse(view: VirtualView, start_node: str, visitor: Callable[[str], None] = None) -> Set[str]:
        visited = set()
        queue = [start_node]
        
        while queue:
            curr = queue.pop(0)
            if curr not in visited:
                visited.add(curr)
                if visitor:
                    visitor(curr)
                    
                for neighbor in view.get_neighbors(curr):
                    if neighbor not in visited:
                        queue.append(neighbor)
                        
        return visited
