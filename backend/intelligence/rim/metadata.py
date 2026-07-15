from pydantic import BaseModel, Field
from typing import Dict, Any, List
from datetime import datetime, timezone

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class RepositoryMetadata(BaseModel):
    name: str = Field(..., description="The name of the repository.")
    path: str = Field(..., description="The file path or URL to the repository.")
    languages: List[str] = Field(default_factory=list, description="Primary languages used in the repository.")
    commit: str = Field("", description="The latest commit hash, if available.")
    branch: str = Field("", description="The checked out branch, if available.")
    created_at: str = Field(default_factory=_now_iso, description="When the repository was first analyzed/created.")
    generated_at: str = Field(default_factory=_now_iso, description="When this specific RIM payload was generated.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extensible metadata for the repository.")
