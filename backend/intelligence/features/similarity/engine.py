from typing import List, Dict, Tuple
from ...capabilities.model import Capability
from ...rim.repository import RepositoryModel
import itertools

class SimilarityEngine:
    """
    Computes a pairwise similarity score between Capabilities.
    """
    def __init__(self, model: RepositoryModel):
        self.model = model

    def compute_similarity(self, cap1: Capability, cap2: Capability) -> float:
        score = 0.0
        
        # 1. Semantic Purpose Match (Very High)
        if cap1.purpose == cap2.purpose:
            score += 0.8
            
        # 2. Shared Keywords (High)
        shared_keywords = set(cap1.keywords).intersection(set(cap2.keywords))
        if shared_keywords:
            score += (len(shared_keywords) * 0.1)
            
        # 3. Structural Link (High)
        # Check if there is an explicit capability relationship between them
        for rel in self.model.capability_relationships.values():
            if (rel.source_id == cap1.id and rel.target_id == cap2.id) or \
               (rel.source_id == cap2.id and rel.target_id == cap1.id):
                score += 0.5
                break
                
        # 4. Same Category (Medium)
        if cap1.category == cap2.category:
            score += 0.2
            
        return min(1.0, score)

    def build_weighted_graph(self) -> Dict[str, Dict[str, float]]:
        graph = {}
        capabilities = list(self.model.capabilities.values())
        
        for cap in capabilities:
            graph[cap.id] = {}
            
        for cap1, cap2 in itertools.combinations(capabilities, 2):
            score = self.compute_similarity(cap1, cap2)
            
            if score > 0.0:
                graph[cap1.id][cap2.id] = score
                graph[cap2.id][cap1.id] = score
                
        return graph
