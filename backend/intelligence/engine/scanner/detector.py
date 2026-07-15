import os
from pathlib import Path
from typing import Dict, Optional

class LanguageDetector:
    """
    Detects programming languages based on file extensions or names.
    """
    EXTENSION_MAP = {
        ".py": "Python",
        ".js": "JavaScript",
        ".jsx": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".go": "Go",
        ".java": "Java",
        ".rs": "Rust",
        ".cs": "C#",
        ".php": "PHP",
        ".rb": "Ruby",
        ".json": "JSON",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".md": "Markdown",
        ".toml": "TOML",
        ".xml": "XML",
        ".html": "HTML",
        ".css": "CSS",
        ".sql": "SQL",
        ".sh": "Shell"
    }

    FILE_NAME_MAP = {
        "Dockerfile": "Dockerfile",
        "Makefile": "Makefile"
    }

    @classmethod
    def detect_language(cls, path: str) -> str:
        """
        Return the detected language for a given file path.
        Returns 'Unknown' if it cannot be determined.
        """
        p = Path(path)
        if p.name in cls.FILE_NAME_MAP:
            return cls.FILE_NAME_MAP[p.name]
            
        ext = p.suffix.lower()
        if ext in cls.EXTENSION_MAP:
            return cls.EXTENSION_MAP[ext]
            
        return "Unknown"
