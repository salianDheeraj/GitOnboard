from typing import List, Dict
from ..rim.repository import RepositoryModel
from .model import Capability, CapabilityRelationship, CapabilityRelationshipType
from .candidates import CandidateSelector
from .inference.modules import infer_keywords_from_entity
from .taxonomy import infer_category_and_purpose_from_keywords
from .consolidation import ConsolidationEngine
import uuid

class CapabilityBuilderEngine:
    """
    Orchestrates the transformation of Entities and Patterns into Semantic Capabilities.
    """
    def run(self, model: RepositoryModel) -> RepositoryModel:
        if not hasattr(model, "capabilities"):
            model.capabilities = {}
        if not hasattr(model, "capability_relationships"):
            model.capability_relationships = {}
            
        selector = CandidateSelector(model)
        candidate_ids = selector.select()
        
        raw_capabilities: List[Capability] = []
        
        # 1. Evidence Collection & Purpose Inference
        for cid in candidate_ids:
            entity = model.entities.get(cid)
            if not entity:
                continue
                
            keywords = infer_keywords_from_entity(entity, model)
            category, purpose = infer_category_and_purpose_from_keywords(keywords)
            
            # Simple responsibility extraction: if it's a function, it performs an action
            responsibilities = []
            if entity.type.value == "FUNCTION":
                responsibilities.append(f"Execute {entity.name}")
                
            cap = Capability(
                id=f"cap:{uuid.uuid4().hex[:8]}",
                purpose=purpose,
                category=category,
                responsibilities=responsibilities,
                keywords=keywords,
                representative_sources=[cid],
                confidence=0.8, # Base confidence
                evidence=[{"source": "Inferred from identifiers and context"}]
            )
            raw_capabilities.append(cap)
            
        # 2. Consolidation
        consolidation_engine = ConsolidationEngine()
        final_capabilities = consolidation_engine.consolidate(raw_capabilities)
        
        for cap in final_capabilities:
            model.capabilities[cap.id] = cap
            
        # 3. Dependency Projection
        # Map raw entity CALLS/USES edges to Capability DEPENDS_ON edges
        entity_to_cap: Dict[str, str] = {}
        for cap in final_capabilities:
            for src in cap.representative_sources:
                entity_to_cap[src] = cap.id
                
        added_edges = set()
        for rel in model.relationships.values():
            if rel.type.value in ["CALLS", "USES", "EXPOSES"]:
                src_cap_id = entity_to_cap.get(rel.source_id)
                tgt_cap_id = entity_to_cap.get(rel.target_id)
                
                if src_cap_id and tgt_cap_id and src_cap_id != tgt_cap_id:
                    edge_key = f"{src_cap_id}->{tgt_cap_id}"
                    if edge_key not in added_edges:
                        added_edges.add(edge_key)
                        
                        rel_type = CapabilityRelationshipType.DEPENDS_ON
                        if rel.type.value == "USES" and model.capabilities[tgt_cap_id].category.value == "PERSISTS":
                            rel_type = CapabilityRelationshipType.PERSISTS
                            
                        cap_rel = CapabilityRelationship(
                            id=f"crel:{uuid.uuid4().hex[:8]}",
                            type=rel_type,
                            source_id=src_cap_id,
                            target_id=tgt_cap_id,
                            metadata={"inferred_from": rel.id}
                        )
                        model.capability_relationships[cap_rel.id] = cap_rel
                        
        return model
