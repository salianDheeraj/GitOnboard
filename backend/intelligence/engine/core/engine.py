from typing import List, Dict
from .context import ProviderContext
from .registry import IntelligenceRegistry
from .recommendations import RecommendationEngine
from .scorecard_engine import ScorecardEngine
from ..model.intelligence import Intelligence, IntelligenceType
from ....rim.repository import RepositoryModel
from ....query.api.base import RepositoryAPI
from ....analysis.engine import AnalysisEngine
from ....store.store import IntelligenceStore

class IntelligenceEngine:
    def __init__(self, 
                 registry: IntelligenceRegistry,
                 query_engine: RepositoryAPI,
                 analysis_engine: AnalysisEngine,
                 store: IntelligenceStore,
                 recommendation_engine: RecommendationEngine,
                 scorecard_engine: ScorecardEngine):
        self.registry = registry
        self.query_engine = query_engine
        self.analysis_engine = analysis_engine
        self.store = store
        self.recommendation_engine = recommendation_engine
        self.scorecard_engine = scorecard_engine
        
    def evaluate(self, repository: RepositoryModel) -> List[Intelligence]:
        context = ProviderContext(
            repository=repository,
            query_engine=self.query_engine,
            analysis_engine=self.analysis_engine,
            store=self.store
        )
        
        results = []
        for provider in self.registry.get_providers():
            intelligence = provider.run(context)
            intelligence = self.recommendation_engine.apply_recommendations(intelligence)
            self.store.save_intelligence(intelligence)
            results.append(intelligence)
            
        return results
        
    def evaluate_types(self, repository: RepositoryModel, types: List[IntelligenceType]) -> List[Intelligence]:
        context = ProviderContext(
            repository=repository,
            query_engine=self.query_engine,
            analysis_engine=self.analysis_engine,
            store=self.store
        )
        
        results = []
        for provider in self.registry.get_providers(types):
            intelligence = provider.run(context)
            intelligence = self.recommendation_engine.apply_recommendations(intelligence)
            self.store.save_intelligence(intelligence)
            results.append(intelligence)
            
        return results
