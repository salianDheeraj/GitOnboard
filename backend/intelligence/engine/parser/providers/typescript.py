"""
TypeScript/JavaScript provider using robust regex-based symbol extraction.
"""
import re
from typing import List, Dict, Any
from .base import LanguageProvider, ParsedFile

# Precompile regexes for performance
RE_IMPORTS_ES6 = re.compile(r"^\s*import\s+(?:type\s+)?(?:{[^}]*}|[\w*]+(?:\s+as\s+\w+)?(?:\s*,\s*{[^}]*})?)\s+from\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
RE_IMPORTS_SIDE_EFFECT = re.compile(r"^\s*import\s+['\"]([^'\"]+)['\"]", re.MULTILINE)
RE_IMPORTS_REQUIRE = re.compile(r"require\(['\"]([^'\"]+)['\"]\)")

RE_CLASS = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:abstract\s+)?class\s+(\w+)(?:<[^>]*>)?(?:\s+extends\s+[\w<>,. ]+)?(?:\s+implements\s+[\w<>,. ]+)?", re.MULTILINE)
RE_INTERFACE = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?interface\s+(\w+)", re.MULTILINE)
RE_FUNC_DECL = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s*\*?\s+(\w+)\s*[(<]", re.MULTILINE)
RE_ARROW_FUNC = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:const|let|var)\s+(\w+)\s*(?::\s*[^=;]+)?\s*=\s*(?:async\s+)?(?:<[^>]*>\s*)?(?:\([^)]*\)|\w+)\s*=>", re.MULTILINE)
RE_FUNC_EXPR = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:const|let|var)\s+(\w+)\s*(?::\s*[^=;]+)?\s*=\s*(?:async\s+)?function", re.MULTILINE)
RE_TYPE_ALIAS = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?type\s+(\w+)\s*(?:<[^>]*)?\s*=", re.MULTILINE)
RE_ENUM = re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:const\s+)?enum\s+(\w+)", re.MULTILINE)

class TypeScriptProvider(LanguageProvider):
    language = "TypeScript"

    def parse(self, file_path: str, source: str) -> ParsedFile:
        language = "TypeScript" if file_path.endswith((".ts", ".tsx")) else "JavaScript"
        
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
        
        def line_of(pos: int) -> int:
            return source[:pos].count("\n") + 1
            
        for m in RE_IMPORTS_ES6.finditer(source):
            imports.append({"module": m.group(1), "line": line_of(m.start()), "type": "import"})
        for m in RE_IMPORTS_SIDE_EFFECT.finditer(source):
            imports.append({"module": m.group(1), "line": line_of(m.start()), "type": "import"})
        for m in RE_IMPORTS_REQUIRE.finditer(source):
            imports.append({"module": m.group(1), "line": line_of(m.start()), "type": "require"})
            
        return imports

    def _extract_symbols(self, source: str, file_path: str) -> List[Dict[str, Any]]:
        symbols = []
        
        def line_of(pos: int) -> int:
            return source[:pos].count("\n") + 1
            
        # Matchers list of tuples: (Regex, Symbol Type)
        matchers = [
            (RE_CLASS, "class"),
            (RE_INTERFACE, "interface"),
            (RE_FUNC_DECL, "function"),
            (RE_ARROW_FUNC, "function"),
            (RE_FUNC_EXPR, "function"),
            (RE_TYPE_ALIAS, "type_alias"),
            (RE_ENUM, "enum"),
        ]
        
        for regex, sym_type in matchers:
            for m in regex.finditer(source):
                symbols.append({"name": m.group(1), "type": sym_type, "line": line_of(m.start()), "file": file_path})
                
        # Deduplicate by name+line
        seen = set()
        deduped = []
        for s in symbols:
            key = (s["name"], s["line"])
            if key not in seen:
                seen.add(key)
                deduped.append(s)
                
        return deduped


class JavaScriptProvider(TypeScriptProvider):
    language = "JavaScript"
