from typing import List
from ..model.intelligence import Intelligence, IntelligenceFinding, Recommendation

class RecommendationEngine:
    """
    Independent functional engine that attaches recommendations to findings.
    """
    def apply_recommendations(self, intelligence: Intelligence) -> Intelligence:
        recommendations = []
        for finding in intelligence.findings:
            if finding.title == "Circular Dependency":
                recommendations.append(
                    Recommendation(
                        finding_id=finding.id,
                        action="Extract Interface",
                        description="Move shared logic to an interface or common module."
                    )
                )
            elif finding.title == "God Module":
                recommendations.append(
                    Recommendation(
                        finding_id=finding.id,
                        action="Split Module",
                        description="Split this module into smaller cohesive features."
                    )
                )
            
        intelligence.recommendations.extend(recommendations)
        return intelligence
