from pydantic import BaseModel, Field
from typing import List, Dict, Set

class RepositoryFile(BaseModel):
    path: str = Field(..., description="The path of the file relative to the repository root.")
    name: str = Field(..., description="The name of the file.")
    extension: str = Field(..., description="The file extension (e.g. '.py', '.ts').")
    size: int = Field(..., description="The size of the file in bytes.")
    language: str = Field("Unknown", description="The detected programming language.")

class Package(BaseModel):
    path: str = Field(..., description="The directory path containing the package.")
    name: str = Field(..., description="The name of the package/module if determinable.")
    type: str = Field(..., description="The package type (e.g. 'npm', 'pip', 'cargo').")

class RepositoryManifest(BaseModel):
    files: List[RepositoryFile] = Field(default_factory=list, description="All discovered non-ignored files.")
    languages: List[str] = Field(default_factory=list, description="All languages detected in the repository.")
    packages: List[Package] = Field(default_factory=list, description="All discovered sub-packages or workspaces.")
