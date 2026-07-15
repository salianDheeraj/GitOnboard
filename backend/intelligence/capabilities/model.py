from pydantic import BaseModel, Field
from typing import List, Dict, Any
from enum import Enum

class CapabilityCategory(str, Enum):
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    PERSISTENCE = "PERSISTENCE"
    COMMUNICATION = "COMMUNICATION"
    BUSINESS_OPERATION = "BUSINESS_OPERATION"
    VALIDATION = "VALIDATION"
    TRANSFORMATION = "TRANSFORMATION"
    CONFIGURATION = "CONFIGURATION"
    SCHEDULING = "SCHEDULING"
    INTEGRATION = "INTEGRATION"
    EVENT_HANDLING = "EVENT_HANDLING"
    CACHING = "CACHING"
    LOGGING = "LOGGING"
    ERROR_HANDLING = "ERROR_HANDLING"

class CapabilityRelationshipType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    USES = "USES"
    TRIGGERS = "TRIGGERS"
    VALIDATES = "VALIDATES"
    PERSISTS = "PERSISTS"
    PUBLISHES = "PUBLISHES"
    CONSUMES = "CONSUMES"
    CONFIGURES = "CONFIGURES"

class CapabilityRelationship(BaseModel):
    id: str
    type: CapabilityRelationshipType
    source_id: str
    target_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Capability(BaseModel):
    id: str
    purpose: str
    category: CapabilityCategory
    responsibilities: List[str]
    keywords: List[str]
    representative_sources: List[str]
    confidence: float
    evidence: List[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(default_factory=dict)
