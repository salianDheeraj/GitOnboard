# Extending the Analysis Framework

The Phase 2 Analysis Framework uses a plugin-based architecture designed around the Open/Closed Principle. This means you can add new analyzers without modifying the existing runner, registry, or other analyzers.

## Creating a New Analyzer

To create a new analyzer:

1. Drop a new Python file into the `src/analysis/plugins/` directory (e.g., `complexity.py`).
2. Implement a concrete subclass of the `Analyzer` abstract base class.
3. The plugin will be automatically discovered and registered by the `AnalyzerRegistry` using its `discover()` method (or it can be manually registered).

### Rules for Analyzers
- Must inherit from `analysis.interfaces.Analyzer`.
- Must implement the `@property def name(self) -> str` to return a unique identifier.
- Must implement `def analyze(self, repository: 'Repository') -> AnalysisResult`.
- **CRITICAL:** Analyzers must ONLY read from the Repository Intelligence Model (RIM). They must not parse source files directly from the filesystem.

### Example Analyzer

```python
from analysis.interfaces import Analyzer
from analysis.models import AnalysisResult, Finding, Severity

class MyCustomAnalyzer(Analyzer):
    @property
    def name(self) -> str:
        return "my_custom_analyzer"

    def analyze(self, repository) -> AnalysisResult:
        findings = []
        
        # Only read from the RIM `repository` object!
        for file in repository.files:
            if getattr(file, "lines", 0) > 1000:
                findings.append(
                    Finding(
                        title="Large File",
                        description=f"File {file.path} is too large.",
                        severity=Severity.WARNING,
                        file_path=file.path
                    )
                )

        return AnalysisResult(
            analyzer_name=self.name,
            findings=findings
        )
```
