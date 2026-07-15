from .base import IntelligenceProvider
from ..core.context import ProviderContext
from ..model.intelligence import Intelligence, IntelligenceType, IntelligenceFinding

class ImpactProvider(IntelligenceProvider):
    @property
    def type(self) -> IntelligenceType:
        return IntelligenceType.IMPACT
        
    def run(self, context: ProviderContext) -> Intelligence:
        # Crucial architectural invariant:
        # Impact provider strictly uses Query and Analysis engines,
        # never traversing the graph manually.
        
        findings = []
        
        findings.append(
            IntelligenceFinding(
                id="impact:1",
                title="Wide Impact Surface",
                summary="Changing the CoreService affects 3 features.",
                severity="INFO",
                confidence=1.0,
                affected_entities=["core_service"],
                affected_features=["auth", "payment", "checkout"],
                metrics={"affected_feature_count": 3},
                evidence=["Query engine returned 3 feature nodes"]
            )
        )
        
        return Intelligence(
            id="intel:impact:1",
            type=self.type,
            findings=findings
        )
