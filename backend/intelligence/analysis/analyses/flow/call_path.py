import time
from typing import Any, Dict, List
from ...rim.repository import RepositoryModel
from ..model.analysis import RepositoryAnalysis
from ..model.result import AnalysisResult
from ..composer.graph_composer import GraphComposer
from ..graph.paths import ShortestPath

class CallPathAnalysis(RepositoryAnalysis):
    @property
    def name(self) -> str:
        return "CallPath"
        
    @property
    def description(self) -> str:
        return "Finds the shortest execution path between two entities."
        
    def execute(self, repository: RepositoryModel, options: Dict[str, Any] = None) -> AnalysisResult[List[str]]:
        start_time = time.time()
        
        options = options or {}
        start_node = options.get("start_node")
        end_node = options.get("end_node")
        
        if not start_node or not end_node:
            raise ValueError("CallPathAnalysis requires 'start_node' and 'end_node' in options.")
            
        composer = GraphComposer(repository)
        view = composer.get_execution_view()
        
        path = ShortestPath.find(view, start_node, end_node)
        
        return AnalysisResult(
            type="PATH_ANALYSIS",
            result=path or [],
            evidence=[{"source": "ShortestPath BFS over Execution View", "start": start_node, "end": end_node}],
            metrics={
                "path_length": len(path) if path else 0
            },
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
