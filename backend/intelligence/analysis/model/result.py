from pydantic import BaseModel, Field
from typing import List, Dict, Any, Generic, TypeVar

T = TypeVar('T')

class AnalysisResult(BaseModel, Generic[T]):
    type: str
    result: T
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: Dict[str, float] = Field(default_factory=dict)
    execution_time_ms: int = 0
