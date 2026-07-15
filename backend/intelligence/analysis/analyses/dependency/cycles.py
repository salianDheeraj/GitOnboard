import time
from typing import Any, Dict, List
from ...rim.repository import RepositoryModel
from ..model.analysis import RepositoryAnalysis
from ..model.result import AnalysisResult
from ..composer.graph_composer import GraphComposer
from ..graph.scc import SCC

class CircularDependencyAnalysis(RepositoryAnalysis):
    @property
    def name(self) -> str:
        return "CircularDependency"
        
    @property
    def description(self) -> str:
        return "Finds cycles in the architecture dependency graph."
        
    def execute(self, repository: RepositoryModel, options: Dict[str, Any] = None) -> AnalysisResult[List[List[str]]]:
        start_time = time.time()
        
        composer = GraphComposer(repository)
        view = composer.get_architecture_view()
        
        components = SCC.find_components(view)
        
        # A component is a cycle if it has > 1 node, or if it has 1 node with a self-loop
        cycles = []
        for comp in components:
            if len(comp) > 1:
                cycles.append(comp)
            elif len(comp) == 1:
                node = comp[0]
                if node in view.get_neighbors(node):
                    cycles.append(comp)
                    
        return AnalysisResult(
            type="CYCLE_DETECTION",
            result=cycles,
            evidence=[{"source": "SCC algorithm over Architecture View", "total_components": len(components)}],
            metrics={
                "cycle_count": len(cycles),
                "max_cycle_length": max([len(c) for c in cycles]) if cycles else 0
            },
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
