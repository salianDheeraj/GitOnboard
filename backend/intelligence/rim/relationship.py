from pydantic import BaseModel, Field
from typing import Dict, Any
from .enums import RelationshipType

class Relationship(BaseModel):
    id: str = Field(..., description="The unique, deterministic stable ID for this relationship.")
    type: RelationshipType = Field(..., description="The type of the relationship (e.g., CALLS, IMPORTS).")
    source_id: str = Field(..., description="The stable ID of the source entity.")
    target_id: str = Field(..., description="The stable ID of the target entity.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extensible metadata specific to this relationship.")
