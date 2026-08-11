import requests
import json
import logging
import os
from sqlalchemy.orm import Session
from backend.intelligence.query_layer import RepositoryQueryEngine

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, base_url=None):
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "llama3.2")

    def generate_summary(self, metadata: dict) -> str:
        """
        Sends the compiled repository metadata to the local Ollama model to generate a summary.
        """
        prompt = self._build_prompt(metadata)
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3}
        }
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "Error: No response generated.")
        except requests.exceptions.HTTPError as e:
            error_text = e.response.text if e.response is not None else "No response body"
            logger.error(f"Ollama HTTP error: {e}, Body: {error_text}")
            raise Exception(f"LLM generation HTTP error: {error_text}")
        except Exception as e:
            import traceback
            logger.error(f"Failed to communicate with Ollama:\n{traceback.format_exc()}")
            raise Exception(f"LLM generation failed: {e}")

    def generate_explanation(self, prompt: str) -> str:
        """
        Sends a generic prompt to the local Ollama model to generate an explanation.
        """
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3}
        }
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "Error: No explanation generated.")
        except requests.exceptions.HTTPError as e:
            error_text = e.response.text if e.response is not None else "No response body"
            logger.error(f"Ollama HTTP error: {e}, Body: {error_text}")
            raise Exception(f"LLM explanation HTTP error: {error_text}")
        except Exception as e:
            import traceback
            logger.error(f"Failed to communicate with Ollama:\n{traceback.format_exc()}")
            raise Exception(f"LLM explanation failed: {e}")

    def _build_prompt(self, metadata: dict) -> str:
        metadata_json = json.dumps(metadata, indent=2)
        return f"""You are a technical documentation writer. You will write a repository summary using ONLY the data provided below.

STRICT RULES — violating any of these is an error:
- Use ONLY the values present in the JSON. Do not invent, guess, or infer anything not explicitly listed.
- Do NOT use placeholder text like [Language 1], [Framework], [Description], etc. If a value is missing, omit that section entirely.
- Do NOT write generic filler sentences like "This repository is a comprehensive project" or "It provides a solid foundation."
- If a field is an empty list, null, or "unknown", skip it — do not mention it at all.
- Write factual, specific sentences using the real values from the JSON.
- Keep the summary concise: 100–250 words maximum.

Output format:
# {metadata.get("repository", {}).get("name", "Repository")} — Summary

Write 2-4 factual bullet-point sections using only data present in the JSON below. Omit any section where the data is empty, null, unknown, or missing.

Repository Metadata:
{metadata_json}

Write the summary now:
"""

llm_service = LLMService()

class EvidenceBackedAIPipeline:
    """
    Layer 8: AI Explanation Pipeline
    Ensures LLM only explains, summarizes, and teaches using deterministic RIM evidence.
    """
    def __init__(self, db: Session, repo_id: str):
        self.query_engine = RepositoryQueryEngine(db, repo_id)

    def process_user_query(self, query_text: str) -> dict:
        intent, symbol_or_route_id = self._detect_intent(query_text)

        evidence = {}
        if intent == "TRACE_EXECUTION":
            evidence = self.query_engine.traceExecution(symbol_or_route_id)
        elif intent == "IMPACT_ANALYSIS":
            evidence = self.query_engine.impactAnalysis(symbol_or_route_id)
        elif intent == "SYMBOL_EXPLANATION":
            evidence = self.query_engine.findDefinition(symbol_or_route_id) or {}
            evidence["callers"] = self.query_engine.findCallers(symbol_or_route_id)
            evidence["callees"] = self.query_engine.findCallees(symbol_or_route_id)
        else:
            evidence = {"general_query": query_text}

        prompt_context = self._build_context(query_text, evidence)
        explanation = self._call_llm(prompt_context)

        return {
            "intent": intent,
            "evidence_used": evidence,
            "explanation": explanation
        }

    def _detect_intent(self, query: str) -> tuple[str, str]:
        q_lower = query.lower()
        if "trace" in q_lower or "flow" in q_lower:
            return "TRACE_EXECUTION", self._extract_id(query)
        elif "impact" in q_lower or "break" in q_lower or "change" in q_lower:
            return "IMPACT_ANALYSIS", self._extract_id(query)
        elif "explain" in q_lower or "what does" in q_lower:
            return "SYMBOL_EXPLANATION", self._extract_id(query)
        return "GENERAL_SEARCH", ""

    def _extract_id(self, query: str) -> str:
        words = query.split()
        for word in words:
            if len(word) == 32:
                return word
        return ""

    def _build_context(self, query: str, evidence: dict) -> str:
        return f"""
You are GitOnboard AI Tutor. Explain the following codebase architecture topic using ONLY the deterministic facts provided below. Do not guess or hallucinate unverified relationships.

User Query: {query}

Verified Codebase Evidence:
{evidence}

Provide a clear, step-by-step technical explanation based on the evidence.
"""

    def _call_llm(self, prompt: str) -> str:
        return llm_service.generate_explanation(prompt)