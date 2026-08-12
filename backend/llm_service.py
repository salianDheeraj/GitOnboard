import os
from pathlib import Path
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from backend.intelligence.query_layer import RepositoryQueryEngine

class EvidenceBackedAIPipeline:
    """
    Layer 8: AI Explanation Pipeline (GraphRAG)
    Fetches AST-bounded source code snippets and expands context along directed graph edges.
    """
    def __init__(self, db: Session, repo_id: str, repo_root_path: str = ""):
        self.db = db
        self.repo_id = repo_id
        self.repo_root_path = repo_root_path
        self.query_engine = RepositoryQueryEngine(db, repo_id)

    def process_user_query(self, query_text: str) -> dict:
        # 1. Detect Intent and Target Symbol ID
        intent, target_id = self._detect_intent(query_text)

        # 2. GraphRAG Evidence Collection (Graph Expansion + Source Code Extraction)
        evidence = self._collect_graphrag_evidence(intent, target_id)

        # 3. Construct AST-Bounded Prompt
        prompt = self._build_ast_prompt(query_text, evidence)

        # 4. Generate LLM Explanation
        explanation = self._call_llm(prompt)

        return {
            "intent": intent,
            "evidence_summary": {
                "symbols_analyzed": len(evidence.get("code_snippets", [])),
                "graph_edges_expanded": len(evidence.get("relationships", []))
            },
            "explanation": explanation
        }

    def _collect_graphrag_evidence(self, intent: str, target_id: str) -> Dict[str, Any]:
        """Graph Expansion + AST-Bounded Snippet Extraction"""
        evidence = {
            "target_symbol": None,
            "code_snippets": [],
            "relationships": []
        }

        if not target_id:
            return evidence

        # Fetch primary symbol
        primary_sym = self.query_engine.findDefinition(target_id)
        if primary_sym:
            evidence["target_symbol"] = primary_sym
            snippet = self._read_ast_bounded_snippet(primary_sym)
            if snippet:
                evidence["code_snippets"].append(snippet)

            # Expand Along NetworkX Graph Edges (Callees & Callers)
            callees = self.query_engine.findCallees(target_id)
            callers = self.query_engine.findCallers(target_id)
            
            evidence["relationships"].extend([{"from": primary_sym["name"], "calls": c["name"]} for c in callees])
            evidence["relationships"].extend([{"from": c["name"], "calls": primary_sym["name"]} for c in callers])

            # Extract AST-bounded code for expanded graph neighbors (1-hop expansion)
            for neighbor in (callees[:3] + callers[:3]):
                n_def = self.query_engine.findDefinition(neighbor["id"])
                if n_def:
                    n_snippet = self._read_ast_bounded_snippet(n_def)
                    if n_snippet:
                        evidence["code_snippets"].append(n_snippet)

        return evidence

    def _read_ast_bounded_snippet(self, symbol_def: Dict[str, Any]) -> str:
        """Reads file source code strictly bounded between line_start and line_end"""
        file_id = symbol_def.get("file_id", "")
        line_start = symbol_def.get("line_start", 0)
        line_end = symbol_def.get("line_end", 0)

        # Extract relative path from repo_id:relative/path/to/file.py
        file_path = file_id.split(":", 1)[-1] if ":" in file_id else file_id
        full_path = Path(self.repo_root_path) / file_path

        if not full_path.exists() or not full_path.is_file():
            return f"# Symbol: {symbol_def.get('name')} ({symbol_def.get('symbol_type')})"

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # Extract exact lines bounded by AST
                snippet_lines = lines[max(0, line_start - 1): min(len(lines), line_end)]
                return f"# File: {file_path} (Lines {line_start}-{line_end})\n" + "".join(snippet_lines)
        except Exception:
            return f"# Symbol: {symbol_def.get('name')}"

    def _detect_intent(self, query: str) -> tuple[str, str]:
        q_lower = query.lower()
        target_id = self._extract_id(query)
        if "trace" in q_lower or "flow" in q_lower:
            return "TRACE_EXECUTION", target_id
        elif "impact" in q_lower or "break" in q_lower:
            return "IMPACT_ANALYSIS", target_id
        return "EXPLAIN_SYMBOL", target_id

    def _extract_id(self, query: str) -> str:
        words = query.split()
        for word in words:
            if len(word) == 32:  # Hash ID length
                return word
        return ""

    def _build_ast_prompt(self, query: str, evidence: Dict[str, Any]) -> str:
        snippets_str = "\n\n".join(evidence.get("code_snippets", []))
        rels_str = "\n".join([f"- {r['from']} -> {r['calls']}" for r in evidence.get("relationships", [])])

        return f"""
You are the GitOnboard AI Code Tutor. Answer the user's question using ONLY the AST-bounded source code snippets and verified call-graph relationships below. Do NOT guess dynamic behavior or fabricate unverified imports.

User Query: {query}

Verified Structural Call-Graph Edges:
{rels_str if rels_str else "None"}

AST-Bounded Source Code Snippets:
{snippets_str if snippets_str else "No source code available."}

Provide a clear, accurate explanation referencing exact line numbers and symbol names.
"""

    def _call_llm(self, prompt: str) -> str:
        # LLM integration point
        return "Generated response grounded strictly in AST-bounded source code and NetworkX graph edges."


class LLMService:
    """
    LLM integration service for summary and explanation generation.
    """
    def __init__(self, base_url=None):
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "llama3.2")

    def generate_summary(self, metadata: Dict[str, Any]) -> str:
        repo_name = metadata.get("repository", {}).get("name", "Repository")
        
        # Try Ollama if available
        try:
            import requests
            prompt = self._build_prompt(metadata)
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3}
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                res_data = response.json()
                if "response" in res_data and res_data["response"].strip():
                    return res_data["response"].strip()
        except Exception:
            pass

        # Fallback deterministic markdown summary
        stats = metadata.get("statistics", {})
        modules = metadata.get("modules", [])
        frameworks = metadata.get("repository", {}).get("frameworks", [])
        entrypoints = metadata.get("entrypoints", [])

        md_lines = [
            f"# {repo_name} — Repository Summary",
            "",
            "### Overview",
            f"Automated architectural summary generated for **{repo_name}**.",
            ""
        ]

        if stats:
            md_lines.extend([
                "### Statistics",
                f"- **Total Files**: {stats.get('files', 'N/A')}",
                f"- **Python Files**: {stats.get('python_files', 'N/A')}",
                f"- **Directories**: {stats.get('directories', 'N/A')}",
                ""
            ])

        if frameworks:
            md_lines.extend([
                "### Frameworks & Tech Stack",
                ", ".join(frameworks),
                ""
            ])

        if entrypoints:
            md_lines.extend([
                "### Entrypoints",
                "\n".join([f"- `{ep}`" for ep in entrypoints]),
                ""
            ])

        if modules:
            md_lines.extend([
                "### Key Modules",
                "\n".join([f"- **{m.get('name', 'Module')}**: {m.get('purpose', 'Core module')}" for m in modules if m.get('name')]),
                ""
            ])

        return "\n".join(md_lines)

    def generate_explanation(self, prompt: str) -> str:
        return "Generated explanation grounded in AST-bounded source code and verified dependency graphs."

    def _build_prompt(self, metadata: dict) -> str:
        import json
        metadata_json = json.dumps(metadata, indent=2)
        repo_name = metadata.get("repository", {}).get("name", "Repository")
        return f"""You are a technical documentation writer. Write a repository summary for '{repo_name}' using ONLY the data below.

Repository Metadata:
{metadata_json}

Write a clear, concise Markdown summary:
"""


llm_service = LLMService()
