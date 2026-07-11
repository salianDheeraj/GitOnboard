from backend.intelligence.repository_model import RepositoryModel
from .graph_view import GraphView

class DependencyGraphView(GraphView):
    def __init__(self, model: RepositoryModel):
        super().__init__()
        # Build view lazily from model relationships
        for entity_id, deps in model.relationships.depends_on.items():
            self._nodes.add(entity_id)
            for dep in deps:
                self._nodes.add(dep)
                self._edges.setdefault(entity_id, []).append(dep)
                self._reverse_edges.setdefault(dep, []).append(entity_id)
