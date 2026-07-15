import time
from typing import Any, Dict, List
from ...rim.repository import RepositoryModel
from ..model.analysis import RepositoryAnalysis
from ..model.result import AnalysisResult
from ..composer.graph_composer import GraphComposer
from ..graph.reachability import Reachability

class DeadCodeAnalysis(RepositoryAnalysis):
    @property
    def name(self) -> str:
        return "DeadCode"
        
    @property
    def description(self) -> str:
        return "Finds entities that cannot be reached by any API route."
        
    def execute(self, repository: RepositoryModel, options: Dict[str, Any] = None) -> AnalysisResult[List[str]]:
        start_time = time.time()
        
        composer = GraphComposer(repository)
        view = composer.get_execution_view()
        
        # 1. Identify all route entities (entrypoints)
        entrypoints = [e.id for e in repository.entities.values() if e.type.value == "ROUTE"]
        
        # 2. Collect everything reachable from any route
        reachable = set()
        for entry in entrypoints:
            reachable.update(Reachability.forward(view, entry))
            
        # 3. Anything not reachable is dead code
        all_nodes = set(view.nodes)
        dead_nodes = all_nodes - reachable
        
        return AnalysisResult(
            type="USAGE_ANALYSIS",
            result=list(dead_nodes),
            evidence=[{"source": "Forward Reachability over Execution View", "entrypoints_used": len(entrypoints)}],
            metrics={
                "total_nodes": len(all_nodes),
                "reachable_nodes": len(reachable),
                "dead_nodes": len(dead_nodes)
            },
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
