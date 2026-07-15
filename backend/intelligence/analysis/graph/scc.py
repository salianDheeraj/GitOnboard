from typing import List, Set, Dict
from ..composer.views.base import VirtualView

class SCC:
    """
    Finds Strongly Connected Components using Kosaraju's Algorithm.
    Useful for cycle detection.
    """
    @staticmethod
    def find_components(view: VirtualView) -> List[List[str]]:
        visited = set()
        stack = []
        
        # Pass 1: Order vertices by finish time
        def _dfs_pass1(node: str):
            visited.add(node)
            for neighbor in view.get_neighbors(node):
                if neighbor not in visited:
                    _dfs_pass1(neighbor)
            stack.append(node)
            
        for node in view.nodes:
            if node not in visited:
                _dfs_pass1(node)
                
        # Pass 2: Process in reverse order on the transposed graph
        visited.clear()
        components = []
        
        def _dfs_pass2(node: str, component: List[str]):
            visited.add(node)
            component.append(node)
            for neighbor in view.get_reverse_neighbors(node):
                if neighbor not in visited:
                    _dfs_pass2(neighbor, component)
                    
        while stack:
            node = stack.pop()
            if node not in visited:
                component = []
                _dfs_pass2(node, component)
                components.append(component)
                
        return components
