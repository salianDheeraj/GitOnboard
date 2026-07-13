from typing import List, Dict, Set, Any
from backend.intelligence.repository_model import RepositoryModel

class DeterministicTracer:
    def __init__(self, model: RepositoryModel):
        self.model = model

    def trace_feature(self, seed_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates a deterministic trace using repository graphs starting from seed nodes.
        seed_nodes: list of metadata dicts from semantic search, e.g., [{"id": "...", "type": "...", "name": "..."}]
        """
        
        # Stage 1: Collect seed IDs
        active_ids = {node["id"] for node in seed_nodes if "id" in node}
        
        # Keep track of the nodes and edges for the trace
        nodes = {}
        edges = []
        
        def add_node(entity_id: str):
            if entity_id in nodes: return
            
            # Find the entity
            entity = None
            entity_type = "unknown"
            
            if entity_id in self.model.entities.functions:
                entity = self.model.entities.functions[entity_id]
                entity_type = "function"
            elif entity_id in self.model.entities.classes:
                entity = self.model.entities.classes[entity_id]
                entity_type = "class"
            elif entity_id in self.model.entities.files:
                entity = self.model.entities.files[entity_id]
                entity_type = "file"
            elif entity_id in self.model.entities.modules:
                entity = self.model.entities.modules[entity_id]
                entity_type = "module"
            
            if entity:
                nodes[entity_id] = {
                    "id": entity_id,
                    "name": getattr(entity, "name", entity_id),
                    "type": entity_type,
                    "file_id": getattr(entity, "file_id", entity_id)
                }

        for sid in active_ids:
            add_node(sid)
            
        # Stage 2: Expand using dependencies (depends_on)
        # Find who depends on our seeds, and what our seeds depend on
        expanded_deps = set()
        for sid in list(active_ids):
            # What sid depends on
            deps = self.model.relationships.depends_on.get(sid, [])
            for dep in deps:
                add_node(dep)
                edges.append({"source": sid, "target": dep, "type": "depends_on"})
                expanded_deps.add(dep)
                
            # Who depends on sid
            for entity_id, entity_deps in self.model.relationships.depends_on.items():
                if sid in entity_deps:
                    add_node(entity_id)
                    edges.append({"source": entity_id, "target": sid, "type": "depends_on"})
                    expanded_deps.add(entity_id)
                    
        active_ids.update(expanded_deps)
        
        # Stage 3: Expand using call graph
        expanded_calls = set()
        for sid in list(active_ids):
            calls = self.model.relationships.calls.get(sid, [])
            for callee in calls:
                add_node(callee)
                edges.append({"source": sid, "target": callee, "type": "calls"})
                expanded_calls.add(callee)
                
            for caller, callees in self.model.relationships.calls.items():
                if sid in callees:
                    add_node(caller)
                    edges.append({"source": caller, "target": sid, "type": "calls"})
                    expanded_calls.add(caller)
                    
        active_ids.update(expanded_calls)
        
        # Stage 4: Use import relationships if they bridge file/module boundaries
        expanded_imports = set()
        for sid in list(active_ids):
            # The node's file
            if sid in nodes:
                file_id = nodes[sid].get("file_id")
                if file_id:
                    imports = self.model.relationships.imports.get(file_id, [])
                    for imp in imports:
                        # Find if any active_id is in the imported file
                        for aid in active_ids:
                            if aid in nodes and nodes[aid].get("file_id") == imp:
                                edges.append({"source": sid, "target": aid, "type": "imports"})
        
        # Stage 5: Merge and sequence the path
        # Simple topological heuristic to order nodes for the linear sequence (Route -> Controller -> etc)
        # We will categorize nodes into typical layers based on naming
        
        layers = {
            "route": 1,
            "controller": 2,
            "service": 3,
            "manager": 4,
            "repository": 5,
            "database": 6,
            "model": 7,
            "response": 8
        }
        
        def get_layer(name: str, file_id: str) -> int:
            name_lower = name.lower()
            file_lower = file_id.lower()
            combined = name_lower + " " + file_lower
            
            if "route" in combined or "api" in combined or "endpoint" in combined:
                return layers["route"]
            if "controller" in combined:
                return layers["controller"]
            if "service" in combined:
                return layers["service"]
            if "manager" in combined:
                return layers["manager"]
            if "repository" in combined or "dao" in combined:
                return layers["repository"]
            if "db" in combined or "database" in combined or "sql" in combined:
                return layers["database"]
            if "model" in combined or "entity" in combined or "schema" in combined:
                return layers["model"]
            if "response" in combined:
                return layers["response"]
            return 99 # unknown layer
            
        ordered_nodes = list(nodes.values())
        ordered_nodes.sort(key=lambda n: get_layer(n["name"], n["file_id"]))
        
        # Extract a simplified flow path
        flow = []
        for n in ordered_nodes:
            layer = get_layer(n["name"], n["file_id"])
            if layer != 99:
                flow.append(n)
        
        # If the heuristic didn't find clear layers, just return the most connected nodes as the flow
        if not flow and ordered_nodes:
            # Sort by degree (number of edges)
            degrees = {nid: 0 for nid in nodes}
            for e in edges:
                if e["source"] in degrees: degrees[e["source"]] += 1
                if e["target"] in degrees: degrees[e["target"]] += 1
            ordered_nodes.sort(key=lambda n: degrees[n["id"]], reverse=True)
            flow = ordered_nodes[:6] # Top 6 most important nodes
        
        return {
            "flow": flow,
            "nodes": list(nodes.values()),
            "edges": edges
        }
