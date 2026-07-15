from ....rim.repository import RepositoryModel
from ....query.api.base import RepositoryAPI
from ....analysis.engine import AnalysisEngine
from ....store.store import IntelligenceStore

class ProviderContext:
    def __init__(self, 
                 repository: RepositoryModel,
                 query_engine: RepositoryAPI,
                 analysis_engine: AnalysisEngine,
                 store: IntelligenceStore):
        self.repository = repository
        self.query_engine = query_engine
        self.analysis_engine = analysis_engine
        self.store = store
