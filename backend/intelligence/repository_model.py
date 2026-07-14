from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any

@dataclass
class RepositoryMetadata:
    repository_name: str
    repository_path: str
    commit_hash: str = ""
    branch: str = ""
    analysis_timestamp: str = ""
    model_version: str = "0.1.0"
    repository_fingerprint: str = ""

@dataclass
class FileNode:
    id: str  # e.g., src/auth/service.py
    path: str
    name: str
    extension: str
    size: int
    is_python: bool

@dataclass
class DirectoryNode:
    id: str
    path: str
    name: str

@dataclass
class ModuleNode:
    id: str
    name: str
    file_id: str

@dataclass
class FunctionNode:
    id: str
    name: str
    file_id: str
    module_id: str
    line_number: int
    docstring: str
    parameters: List[str]
    is_async: bool

@dataclass
class ClassNode:
    id: str
    name: str
    file_id: str
    module_id: str
    line_number: int
    docstring: str

@dataclass
class MethodNode:
    id: str
    name: str
    class_id: str
    file_id: str
    module_id: str
    line_number: int
    docstring: str
    parameters: List[str]
    is_async: bool

@dataclass
class VariableNode:
    id: str
    name: str
    file_id: str
    line_number: int

@dataclass
class ImportNode:
    id: str
    file_id: str
    module_name: str
    alias: Optional[str] = None
    is_local: bool = False

@dataclass
class RepositoryEntities:
    files: Dict[str, FileNode] = field(default_factory=dict)
    directories: Dict[str, DirectoryNode] = field(default_factory=dict)
    modules: Dict[str, ModuleNode] = field(default_factory=dict)
    classes: Dict[str, ClassNode] = field(default_factory=dict)
    functions: Dict[str, FunctionNode] = field(default_factory=dict)
    methods: Dict[str, MethodNode] = field(default_factory=dict)
    variables: Dict[str, VariableNode] = field(default_factory=dict)
    imports: Dict[str, ImportNode] = field(default_factory=dict)

@dataclass
class RepositoryRelationships:
    # file_id -> [class_id, function_id, ...]
    contains: Dict[str, List[str]] = field(default_factory=lambda: {})
    # caller_id (function/method) -> [callee_id, ...]
    calls: Dict[str, List[str]] = field(default_factory=lambda: {})
    # module_id/file_id -> [module_id/file_id, ...]
    imports: Dict[str, List[str]] = field(default_factory=lambda: {})
    # entity_id -> [dependency_id, ...]
    depends_on: Dict[str, List[str]] = field(default_factory=lambda: {})

@dataclass
class RepositoryAnalyses:
    metrics: Optional[Dict[str, Any]] = None
    embeddings: Optional[Any] = None
    architecture: Optional[Dict[str, Any]] = None
    dependency_graph: Optional[Any] = None
    cycles: Optional[List[Any]] = None
    health: Optional[Any] = None
    findings: Optional[List[Any]] = None
    enriched_metadata: Optional[Dict[str, Any]] = None

@dataclass
class AnalysisStatus:
    entities: bool = False
    relationships: bool = False
    metrics: bool = False
    embeddings: bool = False
    architecture: bool = False
    dependencies: bool = False
    cycles: bool = False
    health: bool = False
    findings: bool = False
    enriched_metadata: bool = False

@dataclass
class RepositoryModel:
    """Centralized, immutable model of the repository knowledge."""
    metadata: RepositoryMetadata
    entities: RepositoryEntities = field(default_factory=RepositoryEntities)
    relationships: RepositoryRelationships = field(default_factory=RepositoryRelationships)
    analyses: RepositoryAnalyses = field(default_factory=RepositoryAnalyses)
    analysis_status: AnalysisStatus = field(default_factory=AnalysisStatus)
