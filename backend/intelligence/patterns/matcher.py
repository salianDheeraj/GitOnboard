import re
from typing import Dict, List, Any, Set, Tuple
from .model import Pattern, Evidence, PatternCategory, PatternType
from ..rim.repository import RepositoryModel
from ..graphs.graph_query_service import GraphQueryService
from ..rim.enums import EntityType, RelationshipType
import uuid

class GraphMatcher:
    def __init__(self, model: RepositoryModel):
        self.model = model
        self.query_service = GraphQueryService(model)

    def match_rule(self, rule: dict) -> List[Pattern]:
        patterns = []
        participants_def = rule.get("participants", {})
        relationships_def = rule.get("relationships", [])
        
        # We need an anchor to avoid full graph O(N^k) isomorphism.
        # Find the participant with the most specific type (e.g. ROUTE).
        # Or just start with the first defined participant.
        if not participants_def:
            return patterns
            
        anchor_key = list(participants_def.keys())[0]
        anchor_def = participants_def[anchor_key]
        anchor_type = EntityType(anchor_def["type"])
        
        candidates = self.query_service.find_by_type(anchor_type)
        
        for candidate in candidates:
            if "name_pattern" in anchor_def:
                if not re.search(anchor_def["name_pattern"], candidate.name):
                    continue
                    
            # Try to build a match from this anchor
            match_bindings = {anchor_key: candidate.id}
            
            # DFS/Backtracking for the rest of the relationships
            # For simplicity in this MVP, we will greedily evaluate the relationships definitions
            # Assuming relationships are defined in a connected, directed path from the anchor
            
            evidence_list = []
            is_match = True
            
            for rel_def in relationships_def:
                src_key = rel_def["source"]
                tgt_key = rel_def["target"]
                rel_type_str = rel_def["type"]
                
                # If we don't have the source bound yet, this greedy approach will fail.
                # A true engine does topological sort of the graph pattern.
                if src_key not in match_bindings:
                    is_match = False
                    break
                    
                src_id = match_bindings[src_key]
                
                # Find outgoing relationships of the required type
                outgoing = self.query_service.get_outgoing(src_id)
                found_edge = False
                
                for rel in outgoing:
                    if rel.type.value == rel_type_str:
                        tgt_id = rel.target_id
                        tgt_ent = self.model.entities.get(tgt_id)
                        if not tgt_ent:
                            continue
                            
                        # Check if target entity matches target definition
                        tgt_def = participants_def.get(tgt_key)
                        if tgt_def:
                            if tgt_ent.type.value != tgt_def["type"]:
                                continue
                            if "name_pattern" in tgt_def:
                                if not re.search(tgt_def["name_pattern"], tgt_ent.name):
                                    continue
                                    
                        # Found a match for this edge
                        match_bindings[tgt_key] = tgt_id
                        evidence_list.append(Evidence(
                            relationship_type=rel_type_str,
                            source_id=src_id,
                            target_id=tgt_id,
                            metadata={}
                        ))
                        found_edge = True
                        break # Greedy choice
                        
                if not found_edge:
                    is_match = False
                    break
                    
            if is_match and len(match_bindings) == len(participants_def):
                # Calculate confidence based on rule base
                conf_def = rule.get("confidence", {})
                confidence = float(conf_def.get("base", 1.0))
                
                pattern_type = PatternType(rule["type"])
                pattern_cat = PatternCategory(rule.get("category", "ARCHITECTURAL"))
                
                pattern_id = f"pat:{rule['type'].lower()}:{uuid.uuid4().hex[:8]}"
                
                pattern = Pattern(
                    id=pattern_id,
                    category=pattern_cat,
                    type=pattern_type,
                    participants=list(match_bindings.values()),
                    confidence=confidence,
                    evidence=evidence_list,
                    metadata={"rule_name": rule["name"]}
                )
                patterns.append(pattern)
                
        return patterns
