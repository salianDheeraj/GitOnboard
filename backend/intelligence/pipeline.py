from typing import List, Protocol
from .repository_model import RepositoryModel

class AnalysisStage(Protocol):
    def run(self, model: RepositoryModel) -> None:
        ...

class AnalysisPipeline:
    """Orchestrates the ingestion and analysis of a repository."""

    def __init__(self, builder, relationship_builder):
        self.builder = builder
        self.relationship_builder = relationship_builder
        self.stages: List[AnalysisStage] = []

    def add_stage(self, stage: AnalysisStage):
        self.stages.append(stage)

    def run(self) -> RepositoryModel:
        # Step 1: Build base entities
        model = self.builder.build()
        model.analysis_status.entities = True
        
        # Step 2: Build relationships
        self.relationship_builder.build(model)
        model.analysis_status.relationships = True

        # Step 3: Run extensible analysis stages
        for stage in self.stages:
            stage.run(model)
            
        return model
