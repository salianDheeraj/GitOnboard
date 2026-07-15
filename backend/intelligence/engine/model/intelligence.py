from pydantic import BaseModel
from typing import List, Dict, Any
from enum import Enum

class IntelligenceType(Enum):
    ARCHITECTURE_HEALTH = "Architecture Health"
    IMPACT = "Impact Analysis"
    RISK = "Risk Analysis"
    COVERAGE = "Feature Coverage"

class Recommendation(BaseModel):
    finding_id: str
    action: str
    description: str

class IntelligenceFinding(BaseModel):
    id: str
    title: str
    summary: str
    severity: str
    confidence: float
    affected_entities: List[str]
    affected_features: List[str]
    metrics: Dict[str, Any]
    evidence: List[str]

class Intelligence(BaseModel):
    id: str
    type: IntelligenceType
    findings: List[IntelligenceFinding] = []
    recommendations: List[Recommendation] = []
    metadata: Dict[str, Any] = {}
