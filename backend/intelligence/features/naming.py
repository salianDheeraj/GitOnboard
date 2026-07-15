from typing import List, Dict
from ...rim.repository import RepositoryModel
from ...capabilities.model import CapabilityCategory

class NamingEngine:
    """
    Deterministically names a Feature based on its constituent Capabilities.
    """
    def __init__(self, model: RepositoryModel):
        self.model = model
        
    def name_feature(self, capability_ids: List[str]) -> str:
        # Prioritize Category/Purpose clustering
        categories: Dict[CapabilityCategory, int] = {}
        purposes: Dict[str, int] = {}
        keywords_count: Dict[str, int] = {}
        
        for cid in capability_ids:
            cap = self.model.capabilities.get(cid)
            if not cap:
                continue
                
            categories[cap.category] = categories.get(cap.category, 0) + 1
            purposes[cap.purpose] = purposes.get(cap.purpose, 0) + 1
            
            for kw in cap.keywords:
                keywords_count[kw] = keywords_count.get(kw, 0) + 1
                
        if not categories:
            return "Unknown Feature"
            
        best_cat = max(categories.items(), key=lambda x: x[1])[0]
        
        # If there's a strong purpose, use it
        if purposes:
            best_purpose = max(purposes.items(), key=lambda x: x[1])[0]
            if purposes[best_purpose] > 1 or len(capability_ids) == 1:
                return best_purpose
                
        # Fallback to category title casing
        name = best_cat.value.replace("_", " ").title()
        
        # Check if we can extract from a highly recurring keyword
        if keywords_count:
            best_kw = max(keywords_count.items(), key=lambda x: x[1])[0]
            if keywords_count[best_kw] > 2:
                name = f"{best_kw.title()} {name}"
                
        return name
