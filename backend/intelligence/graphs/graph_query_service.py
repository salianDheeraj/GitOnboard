from typing import List, Dict, Any, Set
from backend.intelligence.repository_model import RepositoryModel

class GraphQueryService:
    def __init__(self, model: RepositoryModel):
        self.model = model

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search for nodes matching the query string."""
        results = []
        q = query.lower()
        
        # Search functions
        for fn in self.model.entities.functions.values():
            if q in fn.name.lower() or q in fn.id.lower():
                results.append({"id": fn.id, "name": fn.name, "type": "function", "file": fn.file_id})
                
        # Search methods
        for m in self.model.entities.methods.values():
            if q in m.name.lower() or q in m.id.lower():
                results.append({"id": m.id, "name": m.name, "type": "method", "file": m.file_id})
                
        # Search classes
        for c in self.model.entities.classes.values():
            if q in c.name.lower() or q in c.id.lower():
                results.append({"id": c.id, "name": c.name, "type": "class", "file": c.file_id})
                
        return results[:50]  # Cap results

    def traverse(self, node_id: str, direction: str = "both", depth: int = 1, max_nodes: int = 50, relationship_type: str = "calls") -> Dict[str, Any]:
        """Traverse the graph from a starting node."""
        if relationship_type != "calls":
            return {"nodes": [], "edges": []}
            
        nodes_to_visit = [(node_id, 0)]
        visited: Set[str] = set()
        edges_out = []
        
        calls = self.model.relationships.calls
        
        # Build reverse calls map for incoming direction
        called_by = {}
        for caller, callees in calls.items():
            for callee in callees:
                called_by.setdefault(callee, []).append(caller)
                
        while nodes_to_visit and len(visited) < max_nodes:
            curr_id, curr_depth = nodes_to_visit.pop(0)
            
            if curr_id in visited:
                continue
                
            visited.add(curr_id)
            
            if curr_depth >= depth:
                continue
                
            # Outgoing
            if direction in ["outgoing", "both"]:
                for callee in calls.get(curr_id, []):
                    edges_out.append({"source": curr_id, "target": callee})
                    if callee not in visited and len(visited) + len(nodes_to_visit) < max_nodes * 2:
                        nodes_to_visit.append((callee, curr_depth + 1))
                        
            # Incoming
            if direction in ["incoming", "both"]:
                for caller in called_by.get(curr_id, []):
                    edges_out.append({"source": caller, "target": curr_id})
                    if caller not in visited and len(visited) + len(nodes_to_visit) < max_nodes * 2:
                        nodes_to_visit.append((caller, curr_depth + 1))
                        
        # Format nodes
        formatted_nodes = []
        for n_id in visited:
            label = n_id.split('::')[-1]
            formatted_nodes.append({"id": n_id, "label": label, "full_name": n_id})
            
        # Deduplicate edges
        unique_edges = []
        seen_edges = set()
        for e in edges_out:
            # Only include edges where both endpoints are in our visited set (to avoid dangling edges)
            if e["source"] in visited and e["target"] in visited:
                edge_sig = (e["source"], e["target"])
                if edge_sig not in seen_edges:
                    seen_edges.add(edge_sig)
                    unique_edges.append({"id": f"e-{e['source']}-{e['target']}", "source": e["source"], "target": e["target"]})
                    
        return {"nodes": formatted_nodes, "edges": unique_edges}
