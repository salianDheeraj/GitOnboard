from .repository import RepositoryModel
from typing import Dict, Any
import json

def serialize_rim(model: RepositoryModel) -> str:
    """
    Serialize the RepositoryModel into the canonical JSON format.
    """
    data = {
        "version": "1.0",
        "repository": model.metadata.model_dump(),
        "entities": [e.model_dump() for e in model.entities.values()],
        "relationships": [r.model_dump() for r in model.relationships.values()]
    }
    return json.dumps(data, indent=2)

def deserialize_rim(json_str: str) -> RepositoryModel:
    """
    Deserialize the canonical JSON format back into a RepositoryModel.
    """
    data = json.loads(json_str)
    
    # Reconstruct dictionary maps from lists
    entities_map = {e["id"]: e for e in data.get("entities", [])}
    relationships_map = {r["id"]: r for r in data.get("relationships", [])}
    
    model_data = {
        "metadata": data.get("repository", {}),
        "entities": entities_map,
        "relationships": relationships_map
    }
    
    return RepositoryModel.model_validate(model_data)
