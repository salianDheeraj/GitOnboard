import requests
import json
import logging

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, base_url=None):
        import os
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self.model = os.environ.get("OLLAMA_MODEL", "llama3.2") # Use llama3.2 (or phi3) as a smaller fallback

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
            "options": {
                "temperature": 0.3
            }
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
            "options": {
                "temperature": 0.3
            }
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
