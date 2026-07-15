from pydantic import BaseModel, Field
from typing import List, Dict, Any
from enum import Enum

class FeatureRelationshipType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    USES = "USES"
    EXTENDS = "EXTENDS"
    PUBLISHES = "PUBLISHES"
    CONSUMES = "CONSUMES"
    CALLS = "CALLS"

class FeatureRelationship(BaseModel):
    id: str
    type: FeatureRelationshipType
    source_id: str
    target_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class FeatureMembership(BaseModel):
    item_id: str
    item_type: str                # 'capability', 'entity', 'route', 'table', 'pattern'
    confidence: float             # [0.0 - 1.0]
    evidence: List[Dict[str, Any]] = Field(default_factory=list)

class Feature(BaseModel):
    id: str
    name: str                     # e.g., "Authentication", "Checkout"
    description: str = ""
    members: List[FeatureMembership] = Field(default_factory=list)
    confidence: float             
    evidence: List[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(default_factory=dict)
