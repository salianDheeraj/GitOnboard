from typing import List, Dict, Any, Set
from backend.intelligence.rim.repository import RepositoryModel
from backend.intelligence.rim.enums import EntityType, RelationshipType

class GraphQueryService:
    def __init__(self, model: RepositoryModel):
        self.model = model

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for nodes matching the query string."""
        results = []
        q = query.lower()
        
        for eid, entity in self.model.entities.items():
            if entity.type in (EntityType.FUNCTION, EntityType.METHOD, EntityType.CLASS):
                if q in entity.name.lower() or q in eid.lower():
                    results.append({
                        "id": eid,
                        "name": entity.name,
                        "type": entity.type.value.lower(),
                        "file": entity.location.repository_path
                    })
                    
        return results[:50]

    def traverse(self, node_id: str, direction: str = "both", depth: int = 1, max_nodes: int = 50, relationship_type: str = "calls") -> Dict[str, Any]:
        """Traverse the graph from a starting node."""
        # Build adjacency maps from flat relationships dict
        outgoing: Dict[str, List[str]] = {}
        incoming: Dict[str, List[str]] = {}
        
        for rel in self.model.relationships.values():
            rel_type = rel.type.value if hasattr(rel.type, 'value') else str(rel.type)
            if relationship_type == "calls" and rel_type != "CALLS":
                continue
            if relationship_type == "imports" and rel_type != "IMPORTS":
                continue
            if relationship_type == "depends_on" and rel_type != "DEPENDS_ON":
                continue
            outgoing.setdefault(rel.source_id, []).append(rel.target_id)
            incoming.setdefault(rel.target_id, []).append(rel.source_id)
                
        nodes_to_visit = [(node_id, 0)]
        visited: Set[str] = set()
        edges_out = []
                
        while nodes_to_visit and len(visited) < max_nodes:
            curr_id, curr_depth = nodes_to_visit.pop(0)
            
            if curr_id in visited:
                continue
                
            visited.add(curr_id)
            
            if curr_depth >= depth:
                continue
                
            if direction in ["outgoing", "both"]:
                for target in outgoing.get(curr_id, []):
                    edges_out.append({"source": curr_id, "target": target})
                    if target not in visited and len(visited) + len(nodes_to_visit) < max_nodes * 2:
                        nodes_to_visit.append((target, curr_depth + 1))
                        
            if direction in ["incoming", "both"]:
                for source in incoming.get(curr_id, []):
                    edges_out.append({"source": source, "target": curr_id})
                    if source not in visited and len(visited) + len(nodes_to_visit) < max_nodes * 2:
                        nodes_to_visit.append((source, curr_depth + 1))
                        
        formatted_nodes = []
        for n_id in visited:
            entity = self.model.entities.get(n_id)
            label = entity.name if entity else n_id.split("::")[-1]
            formatted_nodes.append({"id": n_id, "label": label, "full_name": n_id})
            
        unique_edges = []
        seen_edges = set()
        for e in edges_out:
            if e["source"] in visited and e["target"] in visited:
                edge_sig = (e["source"], e["target"])
                if edge_sig not in seen_edges:
                    seen_edges.add(edge_sig)
                    unique_edges.append({"id": f"e-{e['source']}-{e['target']}", "source": e["source"], "target": e["target"]})
                    
        return {"nodes": formatted_nodes, "edges": unique_edges}
