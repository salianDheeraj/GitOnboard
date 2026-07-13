import requests
import json
import logging

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url
        self.model = "gemma4"

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
        
        return f"""You are an expert technical documentation assistant. 
Your task is to generate a concise, human-readable repository summary based ONLY on the provided JSON metadata.

Instructions:
1. Provide a clear overview of the repository based on its name and contents.
2. List the primary languages and main modules.
3. Highlight key dependencies and entry points.
4. Present the information logically using Markdown headings and bullet points.
5. DO NOT invent facts, infer missing information, or make up dependencies not listed.
6. Omit information that is unavailable rather than guessing.

Repository Metadata:
{metadata_json}

Generate the Markdown summary below:
"""

llm_service = LLMService()
