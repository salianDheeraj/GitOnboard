from typing import List, Dict, Any, Set, Optional
from backend.intelligence.rim.repository import RepositoryModel
from backend.intelligence.rim.enums import EntityType, RelationshipType
from backend.intelligence.rim.entity import Entity
from backend.intelligence.rim.relationship import Relationship

class GraphQueryService:
    def __init__(self, model: RepositoryModel):
        self.model = model
        self._incoming: Dict[str, List[Relationship]] = {}
        self._outgoing: Dict[str, List[Relationship]] = {}
        self._by_type: Dict[EntityType, List[Entity]] = {}
        self._by_name: Dict[str, List[Entity]] = {}

        for entity in self.model.entities.values():
            self._by_type.setdefault(entity.type, []).append(entity)
            self._by_name.setdefault(entity.name, []).append(entity)
            self._incoming.setdefault(entity.id, [])
            self._outgoing.setdefault(entity.id, [])

        for relationship in self.model.relationships.values():
            if relationship.source_id in self._outgoing:
                self._outgoing[relationship.source_id].append(relationship)
            if relationship.target_id in self._incoming:
                self._incoming[relationship.target_id].append(relationship)

    def get_entity(self, id: str) -> Optional[Entity]:
        return self.model.entities.get(id)

    def get_relationships(self, id: str) -> List[Relationship]:
        return self.get_incoming(id) + self.get_outgoing(id)

    def get_incoming(self, id: str) -> List[Relationship]:
        return self._incoming.get(id, [])

    def get_outgoing(self, id: str) -> List[Relationship]:
        return self._outgoing.get(id, [])

    def find_by_type(self, type_: EntityType) -> List[Entity]:
        return self._by_type.get(type_, [])

    def find_by_name(self, name: str) -> List[Entity]:
        return self._by_name.get(name, [])

    def neighbors(self, id: str) -> List[Entity]:
        neighbor_ids = set()
        for relationship in self.get_outgoing(id):
            neighbor_ids.add(relationship.target_id)
        for relationship in self.get_incoming(id):
            neighbor_ids.add(relationship.source_id)

        return [self.get_entity(neighbor_id) for neighbor_id in neighbor_ids if self.get_entity(neighbor_id)]

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
