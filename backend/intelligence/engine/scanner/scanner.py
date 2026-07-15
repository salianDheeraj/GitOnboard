import os
from pathlib import Path
from typing import Set

from .manifest import RepositoryManifest, RepositoryFile, Package
from .detector import LanguageDetector

class RepositoryScanner:
    """
    Scans a repository directory to build a RepositoryManifest.
    Respects common ignore patterns.
    """
    
    DEFAULT_IGNORES = {
        ".git", "node_modules", "venv", ".venv", "env", ".env", 
        "__pycache__", "build", "dist", ".idea", ".vscode"
    }

    def __init__(self, target_dir: str):
        self.target_dir = Path(target_dir).resolve()
        
    def scan(self) -> RepositoryManifest:
        manifest = RepositoryManifest()
        language_set: Set[str] = set()
        
        for root, dirs, files in os.walk(self.target_dir):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in self.DEFAULT_IGNORES]
            
            root_path = Path(root)
            
            # Detect packages (simple heuristic: look for package.json, requirements.txt, Cargo.toml)
            if "package.json" in files:
                rel_path = str(root_path.relative_to(self.target_dir)).replace("\\", "/")
                manifest.packages.append(Package(path=rel_path if rel_path != "." else "/", name=root_path.name, type="npm"))
            elif "requirements.txt" in files or "pyproject.toml" in files:
                rel_path = str(root_path.relative_to(self.target_dir)).replace("\\", "/")
                manifest.packages.append(Package(path=rel_path if rel_path != "." else "/", name=root_path.name, type="pip"))
            elif "Cargo.toml" in files:
                rel_path = str(root_path.relative_to(self.target_dir)).replace("\\", "/")
                manifest.packages.append(Package(path=rel_path if rel_path != "." else "/", name=root_path.name, type="cargo"))
            elif "pom.xml" in files:
                rel_path = str(root_path.relative_to(self.target_dir)).replace("\\", "/")
                manifest.packages.append(Package(path=rel_path if rel_path != "." else "/", name=root_path.name, type="maven"))
                
            for file in files:
                if file.startswith("."):
                    continue
                    
                full_path = root_path / file
                rel_path = str(full_path.relative_to(self.target_dir)).replace("\\", "/")
                
                try:
                    size = full_path.stat().st_size
                except Exception:
                    size = 0
                    
                lang = LanguageDetector.detect_language(rel_path)
                if lang != "Unknown":
                    language_set.add(lang)
                    
                repo_file = RepositoryFile(
                    path=rel_path,
                    name=file,
                    extension=full_path.suffix.lower(),
                    size=size,
                    language=lang
                )
                manifest.files.append(repo_file)
                
        manifest.languages = sorted(list(language_set))
        return manifest
