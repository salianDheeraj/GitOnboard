from typing import List, Dict, Optional
from ..composer.views.base import VirtualView
from .traversal import Traversal

class ShortestPath:
    @staticmethod
    def find(view: VirtualView, start_node: str, end_node: str) -> Optional[List[str]]:
        if start_node == end_node:
            return [start_node]
            
        queue = [start_node]
        visited = {start_node}
        parents = {}
        
        while queue:
            curr = queue.pop(0)
            
            for neighbor in view.get_neighbors(curr):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parents[neighbor] = curr
                    
                    if neighbor == end_node:
                        return Traversal.get_path(parents, end_node)
                        
                    queue.append(neighbor)
                    
        return None

class AllPaths:
    @staticmethod
    def find_all(view: VirtualView, start_node: str, end_node: str, max_depth: int = 10) -> List[List[str]]:
        paths = []
        
        def _dfs(curr: str, path: List[str]):
            if len(path) > max_depth:
                return
            if curr == end_node:
                paths.append(list(path))
                return
                
            for neighbor in view.get_neighbors(curr):
                if neighbor not in path: # Avoid cycles in the current path
                    path.append(neighbor)
                    _dfs(neighbor, path)
                    path.pop()
                    
        _dfs(start_node, [start_node])
        return paths
