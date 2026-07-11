from typing import List, Set, Dict

class GraphView:
    """Lazy graph view over repository relationships."""
    
    def __init__(self):
        self._nodes: Set[str] = set()
        self._edges: Dict[str, List[str]] = {}
        self._reverse_edges: Dict[str, List[str]] = {}

    def get_nodes(self) -> List[str]:
        return list(self._nodes)
        
    def get_edges(self) -> Dict[str, List[str]]:
        return self._edges

    def outgoing(self, node: str) -> List[str]:
        return self._edges.get(node, [])
        
    def incoming(self, node: str) -> List[str]:
        return self._reverse_edges.get(node, [])
        
    def descendants(self, node: str) -> Set[str]:
        visited = set()
        stack = [node]
        while stack:
            curr = stack.pop()
            if curr not in visited:
                visited.add(curr)
                stack.extend(self.outgoing(curr))
        if node in visited:
            visited.remove(node)
        return visited

    def ancestors(self, node: str) -> Set[str]:
        visited = set()
        stack = [node]
        while stack:
            curr = stack.pop()
            if curr not in visited:
                visited.add(curr)
                stack.extend(self.incoming(curr))
        if node in visited:
            visited.remove(node)
        return visited
