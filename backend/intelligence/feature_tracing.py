from typing import List, Dict, Set, Any
from backend.intelligence.rim.repository import RepositoryModel
from backend.intelligence.rim.enums import EntityType, RelationshipType

class DeterministicTracer:
    def __init__(self, model: RepositoryModel):
        self.model = model

    def trace_feature(self, seed_nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates a deterministic trace using repository graphs starting from seed nodes.
        seed_nodes: list of metadata dicts from semantic search, e.g., [{"id": "...", "type": "...", "name": "..."}]
        """
        
        # Build relationship lookup maps from flat relationships dict
        calls_out: Dict[str, List[str]] = {}       # source -> [targets]
        calls_in: Dict[str, List[str]] = {}         # target -> [sources]
        imports_out: Dict[str, List[str]] = {}
        depends_out: Dict[str, List[str]] = {}
        depends_in: Dict[str, List[str]] = {}
        
        for rel in self.model.relationships.values():
            rel_type = rel.type.value if hasattr(rel.type, 'value') else str(rel.type)
            src, tgt = rel.source_id, rel.target_id
            if rel_type == "CALLS":
                calls_out.setdefault(src, []).append(tgt)
                calls_in.setdefault(tgt, []).append(src)
            elif rel_type == "IMPORTS":
                imports_out.setdefault(src, []).append(tgt)
            elif rel_type == "DEPENDS_ON":
                depends_out.setdefault(src, []).append(tgt)
                depends_in.setdefault(tgt, []).append(src)

        # Stage 1: Collect seed IDs
        active_ids: Set[str] = {node["id"] for node in seed_nodes if "id" in node}
        
        nodes: Dict[str, Dict] = {}
        edges: List[Dict] = []
        
        def get_entity_meta(entity_id: str) -> Dict:
            entity = self.model.entities.get(entity_id)
            if not entity:
                return {}
            return {
                "id": entity_id,
                "name": entity.name,
                "type": entity.type.value.lower(),
                "file_id": entity.metadata.get("file_id", entity.location.repository_path),
                "qualified_name": entity.qualified_name or entity.name
            }

        def add_node(entity_id: str):
            if entity_id in nodes or entity_id not in self.model.entities:
                return
            meta = get_entity_meta(entity_id)
            if meta:
                nodes[entity_id] = meta

        for sid in active_ids:
            add_node(sid)
            
        # Stage 2: Expand using depends_on relationships
        expanded_deps: Set[str] = set()
        for sid in list(active_ids):
            for dep in depends_out.get(sid, []):
                add_node(dep)
                edges.append({"source": sid, "target": dep, "type": "depends_on"})
                expanded_deps.add(dep)
            for caller in depends_in.get(sid, []):
                add_node(caller)
                edges.append({"source": caller, "target": sid, "type": "depends_on"})
                expanded_deps.add(caller)
        active_ids.update(expanded_deps)
        
        # Stage 3: Expand using call graph
        expanded_calls: Set[str] = set()
        for sid in list(active_ids):
            for callee in calls_out.get(sid, []):
                add_node(callee)
                edges.append({"source": sid, "target": callee, "type": "calls"})
                expanded_calls.add(callee)
            for caller in calls_in.get(sid, []):
                add_node(caller)
                edges.append({"source": caller, "target": sid, "type": "calls"})
                expanded_calls.add(caller)
        active_ids.update(expanded_calls)
        
        # Stage 4: Add import edges between active nodes
        for sid in list(active_ids):
            if sid in nodes:
                file_id = nodes[sid].get("file_id")
                if file_id:
                    for imp in imports_out.get(file_id, []):
                        for aid in active_ids:
                            if aid in nodes and nodes[aid].get("file_id") == imp:
                                edges.append({"source": sid, "target": aid, "type": "imports"})
        
        # Stage 5: Order nodes into a meaningful flow
        layers = {
            "route": 1, "router": 1, "api": 1, "endpoint": 1,
            "controller": 2,
            "service": 3, "handler": 3,
            "manager": 4, "processor": 4,
            "repository": 5, "dao": 5, "store": 5,
            "db": 6, "database": 6, "sql": 6, "model": 7, "entity": 7, "schema": 7,
            "response": 8, "serializer": 8, "dto": 8
        }
        
        def get_layer(node: Dict) -> int:
            combined = (node.get("name", "") + " " + node.get("file_id", "")).lower()
            for keyword, layer in sorted(layers.items(), key=lambda x: x[1]):
                if keyword in combined:
                    return layer
            return 99
            
        ordered_nodes = list(nodes.values())
        ordered_nodes.sort(key=lambda n: get_layer(n))
        
        # Extract a simplified flow path - prefer nodes with clear layer assignments
        flow = [n for n in ordered_nodes if get_layer(n) != 99]
        
        # If the heuristic didn't find clear layers, use most-connected nodes
        if not flow and ordered_nodes:
            degrees: Dict[str, int] = {nid: 0 for nid in nodes}
            for e in edges:
                if e["source"] in degrees: degrees[e["source"]] += 1
                if e["target"] in degrees: degrees[e["target"]] += 1
            ordered_nodes.sort(key=lambda n: degrees.get(n["id"], 0), reverse=True)
            flow = ordered_nodes[:10]
        
        # If still nothing, just return all seed nodes found
        if not flow:
            flow = [get_entity_meta(sid) for sid in list(active_ids)[:10] if sid in self.model.entities]
        
        return {
            "flow": flow,
            "nodes": list(nodes.values()),
            "edges": edges
        }
