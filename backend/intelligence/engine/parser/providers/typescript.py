"""
TypeScript/JavaScript provider using regex-based symbol extraction.
"""
import re
from typing import List, Dict, Any
from .base import LanguageProvider, ParsedFile


class TypeScriptProvider(LanguageProvider):
    language = "TypeScript"

    def parse(self, file_path: str, source: str) -> ParsedFile:
        language = "TypeScript" if file_path.endswith((".ts", ".tsx")) else "JavaScript"
        
        # Build a synthetic "AST" as structured metadata
        synthetic_ast = {
            "type": "Program",
            "file": file_path,
            "language": language,
            "symbols": self._extract_symbols(source, file_path),
            "imports": self._extract_imports(source),
        }
        
        return ParsedFile(
            file_path=file_path,
            language=language,
            ast=synthetic_ast,
            source=source,
        )

    def _extract_imports(self, source: str) -> List[Dict[str, Any]]:
        imports = []
        # ES6: import X from 'y', import { X } from 'y', import type X from 'y'
        for m in re.finditer(
            r"^import\s+(?:type\s+)?(?:{[^}]*}|[\w*]+(?:\s+as\s+\w+)?(?:\s*,\s*{[^}]*})?)\s+from\s+['\"]([^'\"]+)['\"]",
            source, re.MULTILINE
        ):
            imports.append({"module": m.group(1), "line": source[:m.start()].count("\n") + 1, "type": "import"})
        # Side-effect: import 'y'
        for m in re.finditer(r"^import\s+['\"]([^'\"]+)['\"]", source, re.MULTILINE):
            imports.append({"module": m.group(1), "line": source[:m.start()].count("\n") + 1, "type": "import"})
        # require()
        for m in re.finditer(r"require\(['\"]([^'\"]+)['\"]\)", source):
            imports.append({"module": m.group(1), "line": source[:m.start()].count("\n") + 1, "type": "require"})
        return imports

    def _extract_symbols(self, source: str, file_path: str) -> List[Dict[str, Any]]:
        symbols = []
        
        def line_of(pos: int) -> int:
            return source[:pos].count("\n") + 1
        
        # Classes
        for m in re.finditer(
            r"^(?:export\s+(?:default\s+)?)?(?:abstract\s+)?class\s+(\w+)(?:<[^>]*>)?(?:\s+extends\s+[\w<>, ]+)?(?:\s+implements\s+[\w<>, ]+)?",
            source, re.MULTILINE
        ):
            symbols.append({"name": m.group(1), "type": "class", "line": line_of(m.start()), "file": file_path})

        # Interfaces
        for m in re.finditer(r"^(?:export\s+)?interface\s+(\w+)", source, re.MULTILINE):
            symbols.append({"name": m.group(1), "type": "interface", "line": line_of(m.start()), "file": file_path})

        # Named function declarations
        for m in re.finditer(
            r"^(?:export\s+)?(?:async\s+)?function\s*\*?\s+(\w+)\s*[(<]",
            source, re.MULTILINE
        ):
            symbols.append({"name": m.group(1), "type": "function", "line": line_of(m.start()), "file": file_path})

        # Default export function
        for m in re.finditer(r"^export\s+default\s+(?:async\s+)?function\s+(\w+)", source, re.MULTILINE):
            symbols.append({"name": m.group(1), "type": "function", "line": line_of(m.start()), "file": file_path})

        # Arrow functions and function expressions assigned to const/let/var
        for m in re.finditer(
            r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*(?::\s*[\w<>[\], |&?]+)?\s*=\s*(?:async\s+)?(?:\([^)]*\)|\w+)\s*=>",
            source, re.MULTILINE
        ):
            symbols.append({"name": m.group(1), "type": "function", "line": line_of(m.start()), "file": file_path})

        # Function expression: const X = function(...)
        for m in re.finditer(
            r"^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function",
            source, re.MULTILINE
        ):
            symbols.append({"name": m.group(1), "type": "function", "line": line_of(m.start()), "file": file_path})

        # Type aliases
        for m in re.finditer(r"^(?:export\s+)?type\s+(\w+)\s*(?:<[^>]*)?\s*=", source, re.MULTILINE):
            symbols.append({"name": m.group(1), "type": "type_alias", "line": line_of(m.start()), "file": file_path})

        # Enum
        for m in re.finditer(r"^(?:export\s+)?(?:const\s+)?enum\s+(\w+)", source, re.MULTILINE):
            symbols.append({"name": m.group(1), "type": "enum", "line": line_of(m.start()), "file": file_path})

        # React hooks (useXxx functions)
        for m in re.finditer(
            r"^(?:export\s+)?(?:const|let|var)\s+(use[A-Z]\w*)\s*=\s*(?:async\s+)?\(",
            source, re.MULTILINE
        ):
            symbols.append({"name": m.group(1), "type": "function", "line": line_of(m.start()), "file": file_path})

        # Deduplicate by name+line
        seen = set()
        deduped = []
        for s in symbols:
            key = (s["name"], s["line"])
            if key not in seen:
                seen.add(key)
                deduped.append(s)
        return deduped


# JavaScript uses the same provider
class JavaScriptProvider(TypeScriptProvider):
    language = "JavaScript"
