from typing import Dict, List, Tuple
from .model import CapabilityCategory

# Map keywords to an (Category, Default Purpose)
TAXONOMY_MAP: Dict[str, Tuple[CapabilityCategory, str]] = {
    "login": (CapabilityCategory.AUTHENTICATION, "Authenticate User"),
    "signin": (CapabilityCategory.AUTHENTICATION, "Authenticate User"),
    "auth": (CapabilityCategory.AUTHENTICATION, "Manage Authentication"),
    "jwt": (CapabilityCategory.AUTHENTICATION, "Manage Token"),
    "password": (CapabilityCategory.AUTHENTICATION, "Manage Password"),
    
    "permission": (CapabilityCategory.AUTHORIZATION, "Check Permissions"),
    "role": (CapabilityCategory.AUTHORIZATION, "Manage Roles"),
    "rbac": (CapabilityCategory.AUTHORIZATION, "Manage RBAC"),
    
    "repository": (CapabilityCategory.PERSISTENCE, "Manage Persistence"),
    "database": (CapabilityCategory.PERSISTENCE, "Manage Database"),
    "orm": (CapabilityCategory.PERSISTENCE, "Manage ORM"),
    "save": (CapabilityCategory.PERSISTENCE, "Save Data"),
    
    "api": (CapabilityCategory.COMMUNICATION, "Manage API"),
    "rest": (CapabilityCategory.COMMUNICATION, "Expose REST API"),
    "route": (CapabilityCategory.COMMUNICATION, "Handle Routing"),
    "http": (CapabilityCategory.COMMUNICATION, "Handle HTTP Requests"),
    
    "validate": (CapabilityCategory.VALIDATION, "Validate Input"),
    "schema": (CapabilityCategory.VALIDATION, "Validate Schema"),
    
    "config": (CapabilityCategory.CONFIGURATION, "Manage Configuration"),
    "env": (CapabilityCategory.CONFIGURATION, "Manage Environment"),
    
    "payment": (CapabilityCategory.BUSINESS_OPERATION, "Process Payment"),
    "order": (CapabilityCategory.BUSINESS_OPERATION, "Manage Order"),
}

def infer_category_and_purpose_from_keywords(keywords: List[str]) -> Tuple[CapabilityCategory, str]:
    scores: Dict[CapabilityCategory, int] = {}
    purposes: Dict[CapabilityCategory, List[str]] = {}
    
    for kw in keywords:
        lower_kw = kw.lower()
        for key, (cat, purp) in TAXONOMY_MAP.items():
            if key in lower_kw:
                scores[cat] = scores.get(cat, 0) + 1
                if cat not in purposes:
                    purposes[cat] = []
                purposes[cat].append(purp)
                
    if not scores:
        return CapabilityCategory.BUSINESS_OPERATION, "Perform Business Operation"
        
    best_cat = max(scores.items(), key=lambda x: x[1])[0]
    best_purp = purposes[best_cat][0] # Just pick the first matched purpose for that category
    
    return best_cat, best_purp
