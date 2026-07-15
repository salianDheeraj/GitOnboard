from pydantic import BaseModel, Field
from typing import List, Dict, Any
from enum import Enum

class PatternCategory(str, Enum):
    ARCHITECTURAL = "ARCHITECTURAL"
    COMMUNICATION = "COMMUNICATION"
    FRONTEND = "FRONTEND"
    BACKEND = "BACKEND"
    DATA = "DATA"
    SECURITY = "SECURITY"
    TESTING = "TESTING"

class PatternType(str, Enum):
    MVC = "MVC"
    LAYERED = "LAYERED"
    REPOSITORY = "REPOSITORY"
    REST = "REST"
    REACT_COMPONENT_TREE = "REACT_COMPONENT_TREE"

class Evidence(BaseModel):
    relationship_type: str
    source_id: str
    target_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Pattern(BaseModel):
    id: str
    category: PatternCategory
    type: PatternType
    participants: List[str]
    confidence: float
    evidence: List[Evidence]
    metadata: Dict[str, Any] = Field(default_factory=dict)
