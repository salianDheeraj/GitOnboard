from pydantic import BaseModel, Field
from typing import Optional

class SourceLocation(BaseModel):
    repository_path: str = Field(..., description="The path within the repository.")
    start_line: int = Field(..., description="The 1-indexed start line.")
    end_line: int = Field(..., description="The 1-indexed end line.")
    start_column: Optional[int] = Field(None, description="The 1-indexed start column.")
    end_column: Optional[int] = Field(None, description="The 1-indexed end column.")
    language: str = Field(..., description="The programming language of the file.")
