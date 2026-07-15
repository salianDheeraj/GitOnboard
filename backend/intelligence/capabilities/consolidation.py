from typing import List, Dict
from .model import Capability
import uuid

class ConsolidationEngine:
    """
    Merges capabilities that share the same Purpose and are highly interconnected.
    """
    def consolidate(self, raw_capabilities: List[Capability]) -> List[Capability]:
        consolidated: Dict[str, Capability] = {}
        
        for cap in raw_capabilities:
            # We group by purpose in this simplified heuristic
            # A more advanced version would check call graph connectivity
            key = cap.purpose
            
            if key not in consolidated:
                consolidated[key] = cap
            else:
                existing = consolidated[key]
                
                # Merge lists
                existing.keywords = list(set(existing.keywords + cap.keywords))
                existing.representative_sources = list(set(existing.representative_sources + cap.representative_sources))
                
                # Boost confidence slightly when merged
                existing.confidence = min(1.0, existing.confidence + 0.1)
                
        return list(consolidated.values())
