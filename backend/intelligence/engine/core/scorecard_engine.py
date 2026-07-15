from typing import List, Dict
from pydantic import BaseModel
from ..model.intelligence import Intelligence, IntelligenceType

class Scorecard(BaseModel):
    architecture_score: int
    maintainability_score: int
    risk_score: int

class ScorecardEngine:
    def compute(self, intelligence_results: List[Intelligence]) -> Scorecard:
        arch_score = 100
        risk_score = 100
        
        for intl in intelligence_results:
            for finding in intl.findings:
                if finding.severity == "CRITICAL":
                    if intl.type == IntelligenceType.ARCHITECTURE_HEALTH:
                        arch_score -= 10
                    elif intl.type == IntelligenceType.RISK:
                        risk_score -= 10
                elif finding.severity == "WARNING":
                    if intl.type == IntelligenceType.ARCHITECTURE_HEALTH:
                        arch_score -= 5
                    elif intl.type == IntelligenceType.RISK:
                        risk_score -= 5
                        
        return Scorecard(
            architecture_score=max(0, arch_score),
            maintainability_score=max(0, arch_score), # simplified
            risk_score=max(0, risk_score)
        )
