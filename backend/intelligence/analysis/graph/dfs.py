from typing import List, Set, Callable
from ..composer.views.base import VirtualView
from .traversal import Traversal

class DFS:
    @staticmethod
    def traverse(view: VirtualView, start_node: str, visitor: Callable[[str], None] = None) -> Set[str]:
        visited = set()
        
        def _dfs(node: str):
            if node in visited:
                return
            visited.add(node)
            if visitor:
                visitor(node)
                
            for neighbor in view.get_neighbors(node):
                _dfs(neighbor)
                
        _dfs(start_node)
        return visited
