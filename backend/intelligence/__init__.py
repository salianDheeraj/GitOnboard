"""
Repository Intelligence Core

This package provides a centralized, read-only Repository Intelligence Model
built via an extensible analysis pipeline.
"""

from .repository_model import RepositoryModel
from .pipeline import AnalysisPipeline
from .query_layer import QueryLayer
from .builder import RepositoryBuilder
from .relationships import RelationshipBuilder

__all__ = [
    "RepositoryModel",
    "AnalysisPipeline",
    "QueryLayer",
    "RepositoryBuilder",
    "RelationshipBuilder",
]
