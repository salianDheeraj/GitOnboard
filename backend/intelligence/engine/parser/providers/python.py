import ast
from .base import LanguageProvider, ParsedFile, Diagnostic

class PythonProvider(LanguageProvider):
    language = "Python"

    def parse(self, file_path: str, source: str) -> ParsedFile:
        diagnostics = []
        parsed_ast = None
        
        try:
            parsed_ast = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            diagnostics.append(Diagnostic(
                message=str(e),
                line=e.lineno or 1,
                column=e.offset or 1,
                severity="ERROR"
            ))
            # Fallback or partial AST not easily supported by stdlib `ast`, 
            # but we return what we can or empty AST for now.
            
        return ParsedFile(
            file_path=file_path,
            language=self.language,
            ast=parsed_ast,
            source=source,
            diagnostics=diagnostics
        )
