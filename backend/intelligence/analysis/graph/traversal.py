from typing import List, Set, Dict, Callable
from ..composer.views.base import VirtualView

class Traversal:
    """
    Reusable base utilities for graph traversal.
    """
    @staticmethod
    def get_path(parents: Dict[str, str], end_node: str) -> List[str]:
        path = []
        curr = end_node
        while curr:
            path.append(curr)
            curr = parents.get(curr)
        return path[::-1]
