from pydantic import BaseModel, Field
from typing import Dict
from .entity import Entity
from .relationship import Relationship
from .metadata import RepositoryMetadata

class RepositoryModel(BaseModel):
    metadata: RepositoryMetadata = Field(..., description="Top-level repository metadata.")
    entities: Dict[str, Entity] = Field(default_factory=dict, description="Canonical software artifacts mapped by stable ID.")
    relationships: Dict[str, Relationship] = Field(default_factory=dict, description="Graph edges representing relationships between entities.")
