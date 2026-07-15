"""
Java provider using regex-based symbol extraction.
"""
import re
from typing import List, Dict, Any
from .base import LanguageProvider, ParsedFile


class JavaProvider(LanguageProvider):
    language = "Java"

    def parse(self, file_path: str, source: str) -> ParsedFile:
        synthetic_ast = {
            "type": "CompilationUnit",
            "file": file_path,
            "language": "Java",
            "symbols": self._extract_symbols(source, file_path),
            "imports": self._extract_imports(source),
        }
        return ParsedFile(
            file_path=file_path,
            language="Java",
            ast=synthetic_ast,
            source=source,
        )

    def _extract_imports(self, source: str) -> List[Dict[str, Any]]:
        imports = []
        for m in re.finditer(r"^import\s+(?:static\s+)?([\w.]+)\s*;", source, re.MULTILINE):
            imports.append({"module": m.group(1), "line": source[:m.start()].count("\n") + 1, "type": "import"})
        return imports

    def _extract_symbols(self, source: str, file_path: str) -> List[Dict[str, Any]]:
        symbols = []

        def line_of(pos: int) -> int:
            return source[:pos].count("\n") + 1

        # Classes / Interfaces / Enums
        for m in re.finditer(
            r"(?:^|\n)\s*(?:public|private|protected|abstract|final|static)?\s*(?:public|private|protected|abstract|final|static)?\s*(?:class|interface|enum|@interface)\s+(\w+)",
            source
        ):
            kind = re.search(r"\b(class|interface|enum|@interface)\b", m.group(0))
            sym_type = "class" if kind and kind.group(1) in ("class", "@interface") else (kind.group(1) if kind else "class")
            symbols.append({"name": m.group(1), "type": sym_type, "line": line_of(m.start()), "file": file_path})

        # Methods (simplified: look for type name(...))
        for m in re.finditer(
            r"(?:^|\n)\s*(?:public|private|protected|static|final|synchronized|abstract|native|default)(?:\s+(?:public|private|protected|static|final|synchronized|abstract|native|default))*\s+[\w<>[\], ?]+\s+(\w+)\s*\(",
            source
        ):
            symbols.append({"name": m.group(1), "type": "function", "line": line_of(m.start()), "file": file_path})

        # Deduplicate
        seen = set()
        deduped = []
        for s in symbols:
            key = (s["name"], s["line"])
            if key not in seen:
                seen.add(key)
                deduped.append(s)
        return deduped
