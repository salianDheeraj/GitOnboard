"""
Repository Intelligence Core

This package provides a centralized, read-only Repository Intelligence Model
built via an extensible analysis pipeline.
"""

from .rim.repository import RepositoryModel as _RimRepositoryModel
from .rim_query_layer import QueryLayer
from .pipeline import AnalysisPipeline
from .builder import RepositoryBuilder
from .relationships import RelationshipBuilder

# Expose the RIM RepositoryModel as the primary model type
RepositoryModel = _RimRepositoryModel

__all__ = [
    "RepositoryModel",
    "AnalysisPipeline",
    "QueryLayer",
    "RepositoryBuilder",
    "RelationshipBuilder",
]
