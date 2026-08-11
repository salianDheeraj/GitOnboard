from sqlalchemy.orm import Session
from backend.models.fact_store import RouteRecord, CapabilityRecord, SymbolRecord, RelationshipRecord

class DocumentationGenerator:
    """
    Generates Mermaid architecture diagrams and Markdown documentation directly from RIM facts.
    """
    def __init__(self, db: Session, repo_id: str):
        self.db = db
        self.repo_id = repo_id

    def generate_mermaid_flowchart(self) -> str:
        """Generates a valid Mermaid.js flowchart of routes and handlers."""
        routes = self.db.query(RouteRecord).all()
        mermaid_lines = ["graph TD;"]

        for route in routes:
            handler = self.db.query(SymbolRecord).filter(SymbolRecord.id == route.handler_symbol_id).first()
            handler_name = handler.name if handler else "UnknownHandler"
            
            # Format: Route -> Handler
            route_node = f"Route_{route.id[:6]}[{route.method} {route.path}]"
            handler_node = f"Handler_{route.handler_symbol_id[:6]}[{handler_name}]"
            
            mermaid_lines.append(f"    {route_node} --> {handler_node}")

        return "\n".join(mermaid_lines)

    def generate_readme_summary(self) -> str:
        """Generates a structured architecture summary for onboarded developers."""
        routes = self.db.query(RouteRecord).all()
        capabilities = self.db.query(CapabilityRecord).all()

        markdown = [
            "# 🚀 Architecture Overview",
            "\n## System Capabilities",
        ]

        for cap in capabilities:
            markdown.append(f"- **{cap.name}** ({cap.capability_type}): {cap.evidence_summary}")

        markdown.append("\n## Exposed API Endpoints")
        for r in routes:
            markdown.append(f"- `{r.method} {r.path}`")

        return "\n".join(markdown)