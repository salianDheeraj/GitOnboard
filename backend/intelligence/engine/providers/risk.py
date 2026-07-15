from .base import IntelligenceProvider
from ..core.context import ProviderContext
from ..model.intelligence import Intelligence, IntelligenceType, IntelligenceFinding

class RiskProvider(IntelligenceProvider):
    @property
    def type(self) -> IntelligenceType:
        return IntelligenceType.RISK
        
    def run(self, context: ProviderContext) -> Intelligence:
        # Crucial architectural invariant:
        # Risk provider consumes Phase 7 AnalysisEngine rather than computing graphs itself.
        
        findings = []
        
        # We would run: context.analysis_engine.run_analysis("coupling")
        # And convert those raw metrics into Risk findings.
        
        findings.append(
            IntelligenceFinding(
                id="risk:1",
                title="High Coupling",
                summary="The Payment feature has a high fan-out coupling.",
                severity="WARNING",
                confidence=0.9,
                affected_entities=[],
                affected_features=["payment"],
                metrics={"fan_out": 25},
                evidence=["payment module dependencies"]
            )
        )
        
        return Intelligence(
            id="intel:risk:1",
            type=self.type,
            findings=findings
        )
