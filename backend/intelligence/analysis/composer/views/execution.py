from .base import VirtualView

class ExecutionView(VirtualView):
    """
    Projected graph connecting APIs/Routes down to Entities and Database Tables.
    """
    def _build(self):
        # Flatten relationships into simple edges
        for rel in self.model.relationships.values():
            self.add_edge(rel.source_id, rel.target_id)
