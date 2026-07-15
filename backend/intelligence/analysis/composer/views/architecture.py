from .base import VirtualView

class ArchitectureView(VirtualView):
    """
    Projected graph connecting Features, Patterns, and high-level Dependencies.
    """
    def _build(self):
        # Flatten capability and feature relationships
        if hasattr(self.model, "capability_relationships"):
            for rel in self.model.capability_relationships.values():
                self.add_edge(rel.source_id, rel.target_id)
                
        if hasattr(self.model, "feature_relationships"):
            for rel in self.model.feature_relationships.values():
                self.add_edge(rel.source_id, rel.target_id)
