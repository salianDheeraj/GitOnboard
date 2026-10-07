"""
QA Protocol Adapter: Builds system prompt and parses JSON actions.

Reuses the JSON-action-protocol pattern from ModelAdapter but simplified for Q&A.
Decomposes system prompt into buckets for token accounting.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.ai.schemas import LLMResponse

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    """Tool specification for inclusion in system prompt."""
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema


@dataclass
class SystemPromptParts:
    """Decomposed system prompt for token accounting."""
    grounding_and_protocol_text: str  # static grounding + protocol instructions ("system" bucket)
    tool_catalog_text: str  # tool schemas ("other" bucket)
    rim_metadata_text: str  # RIM metadata block ("rim" bucket, empty for baseline)
    full_text: str  # concatenation actually sent as system message


class QAProtocolAdapter:
    """Builds and parses the action protocol for Q&A (JSON by default, Hermes XML for Qwen3)."""

    @staticmethod
    def is_cloud_model(model_id: str, provider: Optional[str] = None) -> bool:
        """Return True if model/provider is a cloud model using native tool calling."""
        import os
        from backend.config import settings

        if provider in ("groq", "gemini", "openrouter", "ollama_cloud"):
            return True

        if model_id:
            groq_m = getattr(settings, "groq_model", "openai/gpt-oss-120b")
            gemini_m = getattr(settings, "gemini_model", "gemini-2.0-flash")
            openrouter_m = getattr(settings, "openrouter_model", "gpt-4-turbo")
            if model_id in (groq_m, gemini_m, openrouter_m):
                return True

            model_lower = model_id.lower()
            if any(marker in model_lower for marker in ("groq", "gemini", "openrouter", "gpt-", "claude")):
                return True
            if "ollama_cloud" in model_lower or os.environ.get("OLLAMA_IS_CLOUD", "").lower() in ("true", "1"):
                return True

        if getattr(settings, "deployment_type", "").upper() == "PROD":
            return True

        return False

    def __init__(
        self,
        model_id: Optional[str] = None,
        provider: Optional[str] = None,
        native_tools: Optional[bool] = None,
    ):
        """
        Initialize protocol adapter.

        Args:
            model_id: Model identifier (e.g., "qwen/qwen3.8-27b", "gemini-2.0-flash", "qwen3:4b-instruct").
            provider: Provider name (e.g. "groq", "gemini", "openrouter", "ollama").
            native_tools: If specified, explicitly enables/disables native tool calling.
        """
        self.model_id = model_id or ""
        self.provider = provider
        if native_tools is not None:
            self.is_native = native_tools
        else:
            self.is_native = self.is_cloud_model(self.model_id, self.provider)

        # Local Ollama models: Hermes XML for local Qwen, JSON for others
        self.is_local_ollama = not self.is_native
        self.is_qwen = self.is_local_ollama and ("qwen" in self.model_id.lower())


    # Tool usage strategies indexed by tool name
    # These are extracted from the original REPOSITORY_ANALYSIS_RULES and keyed by tool name
    # so that build_system_prompt() can generate a dynamic TOOL USAGE STRATEGY section
    # containing only descriptions for the tools that are actually available
    TOOL_USAGE_STRATEGIES = {
        "get_tree": """**get_tree**: Use for high-level repository orientation, folder hierarchy, and discovering top-level modules.
  - Prefer when you need to locate unfamiliar architectural boundaries or folder layouts.
  - Helps identify which directories to target before detailed search.""",

        "search_repository": """**search_repository**: Primary tool for finding symbols, definitions, references, and files across the repository.
  - Use for general repository discovery and locating where functions, classes, or concepts live.
  - Supports comma-separated multi-query batching (e.g., 'login,auth,token') and offset pagination.""",

        "search_code": """**search_code**: Use for exact lexical text matching, regex patterns, configuration files, and non-symbol code.
  - Use when looking for exact strings, regex patterns, Dockerfiles, YAML/JSON configs, or specific file extensions.
  - Restrict with file_pattern when useful (e.g., "*.json", "Dockerfile*").""",

        "get_file_outline": """**get_file_outline**: Structural navigation tool that outlines all classes, functions, and methods in a file.
  - RECOMMENDED for large files (>200 lines) before calling read_file to identify exact symbol line ranges.
  - Avoids reading unnecessary code by giving you line-bounded anchors first.""",

        "query_rim": """**query_rim**: Bounded graph investigation tool for structural relationships (CALLS, IMPORTS, INHERITS, CONTAINS, ROUTE_HANDLER, DATABASE_ACCESS, GENERIC).
  - Use when the question asks about callers, callees, dependencies, imports, inheritance, route handlers, or database table access.
  - Use scope='LOCAL' (default, 1 hop) for direct callers/callees.
  - Use scope='NEIGHBORHOOD' (depth 1-3) for multi-hop tracing across components.
  - If query_rim returns NO_STATIC_EDGE_FOUND, do NOT assume the relationship does not exist; dynamic JS/TS execution or callbacks may exist. Follow the suggested fallback (search_repository) to inspect the implementation.""",

        "read_file": """**read_file**: Authoritative tool for inspecting actual code implementation and verifying behavior.
  - Primary tool for understanding HOW something works.
  - Always specify start_line and end_line covering the relevant block (safe limit is 250 lines max per call).
  - For large files (>200 lines), run get_file_outline first to find exact symbol line ranges instead of reading blindly.
  - Use optional context_lines to include surrounding context without making extra calls.
  - Never make implementation claims from search or graph results alone without reading source code.""",
    }

    # Shared behavioral/grounding rules for all tool-calling formats
    REPOSITORY_ANALYSIS_RULES = """You are an expert software repository analysis assistant.

Your job is to answer the user's question accurately using the repository tools available to you.

## CORE PRINCIPLE

For questions about this repository, prefer repository evidence over general knowledge.
Do not invent repository-specific facts.
When making a claim about how this codebase works, base it on information obtained from the repository tools.
You may use general programming knowledge to interpret repository evidence and explain concepts, but clearly distinguish inference from facts directly observed.

## REPOSITORY CONTEXT & TOOL SELECTION

The repository being analyzed may be any software project, library, data science workflow, Jupyter notebook collection, or full-stack application.
Do NOT assume any specific framework (e.g., FastAPI, Django, Spring), database, or architecture unless directly observed via repository tools.

### INTENT-BASED TOOL SELECTION

Select tools based on what evidence you need rather than following a rigid predetermined sequence:
- **Repository orientation & architecture overview**: Call `get_tree` to discover structure.
- **Finding symbols, definitions, & files**: Call `search_repository`.
- **Exact text, regex patterns, & configs (YAML, JSON, Docker)**: Call `search_code`.
- **Large-file navigation (>200 lines)**: Call `get_file_outline` to locate symbol line boundaries before reading.
- **Relationships, callers, callees, dependencies, & execution flow**: Call `query_rim` (LOCAL for 1-hop, NEIGHBORHOOD for multi-hop tracing).
- **Implementation verification**: Call `read_file` with targeted `start_line` and `end_line` (plus optional `context_lines`).

Use the smallest set of tools that provides sufficient evidence. Do not call extra tools merely to appear thorough.

### CODE INSPECTION & EVIDENCE MANDATE
1. **Search tools and query_rim return pointers, metadata, and snippets**, NOT full implementations.
2. **Authoritative Verification**: When you identify relevant files and lines (e.g. from search, file outline, or graph relationships), call `read_file` on that specific line range to inspect the actual implementation before concluding.
3. **Graph Uncertainty & Dynamic Code**: `query_rim` operates on static analysis. If `query_rim` returns `NO_STATIC_EDGE_FOUND`, it means no static edge was found in the graph. It does NOT mean "the relationship definitely does not exist." Dynamic JavaScript/TypeScript constructs (callbacks, arrow functions, middleware pipelines, dynamic imports) may still connect them. Follow the suggested fallback (`search_repository` -> `read_file`) to verify.
4. **Negative and Absence Claims**: Claims that something is missing, incomplete, or absent (e.g. "There is no vector database" or "authenticate is not called") require thorough search evidence across relevant directories before concluding absence.
5. **Notebooks are Code**: In data science, machine learning, and AI repositories, `.ipynb` files contain first-class code. Treat them as full code files.

## INVESTIGATION APPROACH

For every repository-specific question:
1. **Understand** exactly what the user is asking.
2. **Select appropriate tools** to investigate the question based on intent (search for files/symbols, outline large files, query relationships, or inspect implementation).
3. **Verify with read_file** to examine actual source code before answering questions about how features work.
4. **Synthesize & Answer**: Once the necessary evidence is collected and understood, provide the final answer immediately. Do not make extra tool calls if you already have the evidence.
5. If the repository truly does not contain enough evidence to answer confidently, state what was searched and what could not be found. Do not fabricate missing components.

## PARALLEL TOOL CALLS

When multiple tool calls are independent, use them in the same turn.
When one call depends on another's result, perform sequentially.
Do not make additional calls merely to appear thorough.
Optimize for accurate evidence with the fewest useful tool calls.

## EVIDENCE AND REASONING

Clearly separate:
1. Facts directly observed in repository/tool results
2. Reasonable conclusions derived from those facts
3. General programming knowledge

Do not present an inference as if it were directly observed.
For important conclusions, prefer corroborating evidence from source code or multiple tool results.
When evidence conflicts: investigate the conflicting evidence, prefer more direct/current evidence.
When evidence is incomplete: state what was established and what could not be established. Do not fabricate missing information.

## ANSWER QUALITY

The final answer should directly answer the user's question rather than describing the investigation process.
Use Markdown with:
- Concise answer first
- Headings when they improve organization
- Bullet points for multiple findings
- Code formatting for symbols, files, commands, configuration values
- File paths and line references when available
- Short code snippets only when they materially clarify

Do not include statements like:
- "I searched the repository..."
- "Let me investigate..."
- "I used the following tools..."

Unless the user specifically asks about the investigation process.

For complex questions, structure as:
1. **Answer / Summary**
2. **How it works**
3. **Relevant code / components**
4. **Evidence**
5. **Caveats** (if applicable)

For simple questions, answer simply.

## USER INTENT

Answer the question the user actually asked.
Do not perform broad repository exploration when a narrow lookup can answer the question.
If ambiguous, ask a concise clarification question. Otherwise, make the most reasonable interpretation and proceed."""

    GROUNDING_RULES_JSON = f"""{REPOSITORY_ANALYSIS_RULES}

## RESPONSE PROTOCOL (JSON FORMAT)

=== MANDATORY RESPONSE PROTOCOL (READ FIRST) ===
EVERY response MUST be EXACTLY ONE JSON object with NO extra text.
ONLY TWO VALID ACTIONS EXIST:
  1. {{"action": "tool_call", "tool_name": "<NAME>", "arguments": {{...}}}}
  2. {{"action": "final_answer", "answer": "..."}}

⚠️  CRITICAL RULE: action MUST ALWAYS be the STRING "tool_call" or "final_answer"
⚠️  NEVER use tool name as action: {{"action": "search_code"}} is WRONG
⚠️  ALWAYS use: {{"action": "tool_call", "tool_name": "search_code"}} is CORRECT

YOUR TASK (MANDATORY):
Use tools to investigate repository questions and gather evidence. Provide a final answer once you have sufficient information.

1. Analyze the user's question
2. Determine what tools you need to answer it
3. Call those tools (one per turn) to gather repository evidence
4. Once you have enough evidence from tools, provide your final answer
5. If you're confident in your answer, provide it immediately - do NOT make unnecessary additional tool calls

⚠️  Avoid redundant tool calls. Stop calling tools once you have sufficient evidence to answer the question confidently.

RESPONSE FORMAT (MANDATORY - STRICT JSON ONLY):
Each turn, output EXACTLY ONE complete JSON object with NO extra text:

For tool calls, ALWAYS use this structure:
{{"action": "tool_call", "tool_name": "<TOOL_NAME>", "arguments": {{<ARGUMENTS>}}}}

When done analyzing:
{{"action": "final_answer", "answer": "Your answer based on tools"}}

EXECUTION RULES:
1. ONE tool call per turn - wait for results before taking next action
2. Use the fewest tool calls necessary to answer accurately
3. Once available repository evidence is sufficient, provide your answer
4. Base repository-specific claims on tool results, never on general knowledge
5. JSON ONLY: Output ONLY the JSON object, with NO text before or after it
6. NO EXPLANATIONS: Do not add "Let me search..." or "I found..." - just output the JSON"""

    GROUNDING_RULES_HERMES = f"""{REPOSITORY_ANALYSIS_RULES}

## RESPONSE PROTOCOL (HERMES XML FORMAT)

=== MANDATORY RESPONSE PROTOCOL (Hermes XML Format) ===
EVERY response MUST use HERMES XML TOOL CALLING format. Output EITHER:
  1. A tool call in XML format (see examples below)
  2. A final answer wrapped in tags

YOUR TASK (MANDATORY):
Use tools to investigate repository questions and gather evidence. Provide a final answer once you have sufficient information.

1. Analyze the user's question
2. Determine what tools you need to answer it
3. Call those tools (one per turn) to gather repository evidence
4. Once you have enough evidence from tools, provide your final answer
5. If you're confident in your answer, provide it immediately - do NOT make unnecessary additional tool calls

⚠️  Avoid redundant tool calls. Stop calling tools once you have sufficient evidence to answer the question confidently.

RESPONSE FORMAT (MANDATORY - HERMES XML ONLY):
For tool calls, use EXACTLY this structure:
<tool_call>
<invoke name="TOOL_NAME">
<parameter name="param_name">value</parameter>
</invoke>
</tool_call>

When done analyzing, use:
<tool_call>
<invoke name="final_answer">
<parameter name="answer">Your answer based on tools</parameter>
</invoke>
</tool_call>

EXECUTION RULES:
1. ONE tool call per turn - wait for results before taking next action
2. Use the fewest tool calls necessary to answer accurately
3. Once available repository evidence is sufficient, provide your answer
4. Base repository-specific claims on tool results, never on general knowledge
5. Output ONLY the XML tool call, with NO text before or after it
6. NO EXPLANATIONS: Do not add "Let me search..." or "I found..." - just output the XML"""

    GROUNDING_RULES_NATIVE = f"""{REPOSITORY_ANALYSIS_RULES}

## RESPONSE PROTOCOL (NATIVE TOOL CALLING)

YOUR TASK:
Use the available tools natively to investigate repository questions and gather evidence. Provide a final answer once you have sufficient information.

1. Analyze the user's question.
2. Call tools natively whenever you need to inspect files, search code, or query symbols and relationships.
3. Once you have enough evidence from tools, provide your final answer directly in Markdown.
4. If you're confident in your answer, provide it immediately - do NOT make unnecessary additional tool calls.
5. Base repository-specific claims on tool results, never on general assumptions.
"""

    @property
    def GROUNDING_RULES(self) -> str:
        """Return format-specific grounding rules based on model type."""
        if self.is_native:
            return self.GROUNDING_RULES_NATIVE
        return self.GROUNDING_RULES_HERMES if self.is_qwen else self.GROUNDING_RULES_JSON

    def _build_tool_usage_strategy(self, tool_specs: List[ToolSpec]) -> str:
        """
        Build TOOL USAGE STRATEGY section dynamically from available tools only.

        This ensures that baseline runs (include_rim=False) only contain strategy
        descriptions for the 3 baseline tools, and RIM runs contain descriptions
        for all available tools. This prevents the LLM from learning about tools
        it cannot use.

        Args:
            tool_specs: List of ToolSpec objects for available tools

        Returns:
            Formatted TOOL USAGE STRATEGY section string
        """
        if not tool_specs:
            return "## TOOL USAGE STRATEGY\n\nNo tools available.\n"

        # Extract tool names from specs
        available_tool_names = {spec.name for spec in tool_specs}

        # Build strategy lines for only available tools
        strategy_lines = ["## TOOL USAGE STRATEGY\n"]
        for spec in tool_specs:
            if spec.name in self.TOOL_USAGE_STRATEGIES:
                strategy_lines.append(self.TOOL_USAGE_STRATEGIES[spec.name])
                strategy_lines.append("")  # Blank line between tools

        return "\n".join(strategy_lines)

    def build_system_prompt(self, tool_specs: List[ToolSpec], rim_metadata_block: Optional[str]) -> SystemPromptParts:
        """
        Build decomposed system prompt with separate buckets for token accounting.

        CRITICAL: Tool usage strategy is built DYNAMICALLY from tool_specs only.
        This ensures baseline runs (include_rim=False) only see strategy for their 3 tools,
        preventing the LLM from learning about unavailable RIM-only tools.

        Args:
            tool_specs: List of available tools (baseline + RIM-specific if RIM side)
            rim_metadata_block: RIM metadata facts (None or empty string for baseline)

        Returns:
            SystemPromptParts with decomposed text for token counting
        """
        # 1. Grounding rules + protocol (constant, already excludes tool strategy)
        grounding = self.GROUNDING_RULES

        # 2. Build tool usage strategy DYNAMICALLY from available tools only
        # This is the critical fix: baseline gets strategy for 3 tools, RIM gets strategy for 9
        tool_usage_strategy = self._build_tool_usage_strategy(tool_specs)

        # 3. Tool catalog (JSON schema definitions)
        tool_catalog = self._build_tool_catalog(tool_specs)

        # 4. RIM metadata (baseline gets empty, RIM side gets facts)
        rim_section = ""
        if rim_metadata_block:
            rim_section = f"""
### RIM_METADATA

Repository Intelligence Graph facts (structural relationships):

{rim_metadata_block}

**WHEN TO USE QUERY_RIM:**
Use `query_rim` when the question involves relationships, callers/callees, dependencies, or connections between repository entities:
- CALLS: functions called by or calling an entity
- IMPORTS: module dependencies (incoming and outgoing)
- INHERITS: class inheritance and base classes
- CONTAINS: symbols declared within a file or class
- ROUTE_HANDLER: route handlers mapped to HTTP endpoints
- DATABASE_ACCESS: database tables or models accessed by code

Use scope='LOCAL' for direct 1-hop relationships, 'NEIGHBORHOOD' (depth 1-3) for multi-hop tracing, and 'GLOBAL' when repository-wide relationship inspection is required.

If query_rim returns NO_STATIC_EDGE_FOUND, dynamic code may be present; use search_repository and read_file to inspect the implementation directly."""
        else:
            rim_section = ""  # baseline gets no RIM section at all

        # 5. Combine all sections in order: grounding → strategy → catalog → RIM
        full_text = f"""{grounding}

{tool_usage_strategy}
{tool_catalog}{rim_section}"""

        return SystemPromptParts(
            grounding_and_protocol_text=grounding,
            tool_catalog_text=tool_catalog,
            rim_metadata_text=rim_section,
            full_text=full_text,
        )

    def _build_tool_catalog(self, tool_specs: List[ToolSpec]) -> str:
        """Build the AVAILABLE TOOLS section of the prompt."""
        if not tool_specs:
            return "### AVAILABLE TOOLS\n(None)"

        lines = ["### AVAILABLE TOOLS\n"]
        for spec in tool_specs:
            lines.append(f"**{spec.name}**: {spec.description}")
            lines.append(f"Arguments: {self._format_json_schema(spec.parameters)}")
            lines.append("")

        return "\n".join(lines)

    def _format_json_schema(self, schema: Dict[str, Any]) -> str:
        """Format JSON schema as inline text."""
        import json
        try:
            return json.dumps(schema, indent=2)
        except:
            return str(schema)

    def parse_response(self, text: str) -> Dict[str, Any]:
        """
        Parse LLM response for action (JSON or Hermes XML depending on model).

        For Qwen models: tries Hermes XML first, falls back to JSON if XML not found.
        This handles non-deterministic LLM behavior where context degradation causes
        format switching (early turns: Hermes XML, later turns: JSON).

        Returns:
            {
                "action": "tool_call" | "final_answer" | "malformed",
                "tool_name": "...",  # if tool_call
                "arguments": {...},  # if tool_call
                "answer": "...",  # if final_answer
                "error": "...",  # if malformed
            }
        """
        if self.is_qwen:
            # Try Hermes format first (native for Qwen)
            result = self._parse_hermes_response(text)
            # If Hermes parsing failed but looks like it tried, don't fall back
            if result["action"] != "malformed" or "<tool_call>" in text:
                return result
            # Context degradation: LLM reverted to JSON, try JSON format as fallback
            logger.debug(f"[parse_response] Hermes parse failed, trying JSON fallback for Qwen")
            return self._parse_json_response(text)
        else:
            return self._parse_json_response(text)

    def parse_response_from_llm_response(self, llm_response: "LLMResponse") -> Dict[str, Any]:
        """
        Normalize native tool calls or text-parsed tool calls into a uniform list format.

        For Groq, Gemini, OpenRouter, and Ollama Cloud (native tool calling):
          - Always use native tool calling as the primary method.
          - If llm_response.tool_calls is populated, takes the first tool call.
          - If no tool calls, returns final_answer directly with llm_response.content.
          - NO text fallback to Hermes XML or JSON.

        Only for local Ollama models:
          - Uses Hermes XML (for local Qwen) or JSON action protocol parsing on llm_response.content.
        """
        is_native = self.is_native or self.is_cloud_model(llm_response.model, llm_response.provider)

        if is_native:
            if llm_response.tool_calls:
                tc = llm_response.tool_calls[0]  # Take only first tool call
                return {
                    "action": "tool_call",
                    "tool_calls": [
                        {"tool_name": tc.tool_name, "arguments": tc.parameters}
                    ],
                    "tool_name": tc.tool_name,
                    "arguments": tc.parameters,
                }
            # No tool call made -> This is a final answer directly (NO FALLBACK)
            return {
                "action": "final_answer",
                "answer": llm_response.content,
            }

        # Local Ollama model behavior (Hermes XML / JSON text protocol):
        if llm_response.tool_calls:
            tc = llm_response.tool_calls[0]  # Take only first tool call
            return {
                "action": "tool_call",
                "tool_calls": [
                    {"tool_name": tc.tool_name, "arguments": tc.parameters}
                ],
                "tool_name": tc.tool_name,
                "arguments": tc.parameters,
            }
        result = self.parse_response(llm_response.content)
        if result.get("action") == "tool_call":
            return {
                "action": "tool_call",
                "tool_calls": [
                    {"tool_name": result["tool_name"], "arguments": result["arguments"]}
                ],
                "tool_name": result["tool_name"],
                "arguments": result["arguments"],
            }
        return result

    def _parse_hermes_response(self, text: str) -> Dict[str, Any]:
        """Parse Hermes XML tool calling format (for Qwen models)."""
        import re
        import json

        # Look for <tool_call> ... </tool_call> blocks
        tool_call_match = re.search(r'<tool_call>(.*?)</tool_call>', text, re.DOTALL)
        if not tool_call_match:
            logger.debug(f"[parse_hermes] No <tool_call> block found in response: {text[:100]}")
            return {"action": "malformed", "error": "no <tool_call> block found"}

        tool_call_content = tool_call_match.group(1)

        # Extract invoke name: <invoke name="tool_name">
        invoke_match = re.search(r'<invoke name="([^"]+)">', tool_call_content)
        if not invoke_match:
            logger.debug(f"[parse_hermes] No <invoke> with name attribute found")
            return {"action": "malformed", "error": "no <invoke name=...> found"}

        invoke_name = invoke_match.group(1).strip()

        # Special case: final_answer
        if invoke_name == "final_answer":
            # Extract answer from <parameter name="answer">...</parameter>
            param_match = re.search(r'<parameter name="answer">(.*?)</parameter>', tool_call_content, re.DOTALL)
            answer = param_match.group(1).strip() if param_match else text
            return {
                "action": "final_answer",
                "answer": answer,
            }

        # Regular tool call: extract parameters
        KNOWN_TOOLS = {
            "search_code", "search_repository", "get_file_outline",
            "query_rim", "read_file", "get_tree"
        }

        if invoke_name not in KNOWN_TOOLS:
            logger.debug(f"[parse_hermes] Unknown tool: {invoke_name}")
            return {"action": "malformed", "error": f"unknown tool: {invoke_name}"}

        # Extract all parameters: <parameter name="key">value</parameter>
        arguments = {}
        param_pattern = r'<parameter name="([^"]+)">([^<]*)</parameter>'
        for match in re.finditer(param_pattern, tool_call_content):
            param_name = match.group(1).strip()
            param_value = match.group(2).strip()

            # Try to parse as JSON if it looks like JSON
            if param_value.startswith('{') or param_value.startswith('['):
                try:
                    param_value = json.loads(param_value)
                except json.JSONDecodeError:
                    pass  # Keep as string if not valid JSON

            arguments[param_name] = param_value

        logger.debug(f"[parse_hermes] Parsed tool_call: {invoke_name} with {len(arguments)} params")
        return {
            "action": "tool_call",
            "tool_name": invoke_name,
            "arguments": arguments,
        }

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON format responses."""
        import json
        import re

        # Try to extract JSON object from response.
        # Search for '{' and attempt to parse from each position until successful.
        # This handles nested JSON (e.g., arguments with nested dicts).
        obj = None
        for match in re.finditer(r'\{', text):
            start_pos = match.start()
            # Find the matching closing brace by counting braces
            brace_count = 0
            end_pos = start_pos
            for i in range(start_pos, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_pos = i + 1
                        break

            if brace_count == 0:  # Found matching close brace
                try:
                    # Try to parse just this JSON object
                    json_str = text[start_pos:end_pos]
                    obj = json.loads(json_str)
                    if isinstance(obj, dict):
                        # Successfully parsed a JSON object
                        action = obj.get("action", "").lower()
                        if action in ["tool_call", "final_answer"]:
                            # This is a valid action object
                            break
                except json.JSONDecodeError:
                    # This position didn't yield valid JSON, try next {
                    obj = None
                    continue

        if obj is None or not isinstance(obj, dict):
            logger.debug(f"No valid JSON action object found in response: {text[:100]}")
            return {
                "action": "malformed",
                "error": "no valid JSON action object found",
            }

        action = obj.get("action", "").lower()

        # FALLBACK: Detect and fix malformed responses where LLM put tool name as action
        # This happens with small models like Qwen 3 4B that don't follow complex instructions
        # Pattern: {"action": "search_code", "arguments": {...}} should be tool_call
        KNOWN_TOOLS = {
            "search_code", "search_repository", "get_file_outline",
            "query_rim", "read_file", "get_tree"
        }
        if action in KNOWN_TOOLS and obj.get("arguments"):
            # LLM mistakenly used tool name as action. Correct it.
            logger.warning(f"[parse_response] Correcting malformed response: action={action} (should be tool_call)")
            obj["tool_name"] = action
            obj["action"] = "tool_call"
            action = "tool_call"

        if action == "tool_call":
            tool_name = obj.get("tool_name", "").strip()
            arguments = obj.get("arguments", {})

            if not tool_name:
                return {
                    "action": "malformed",
                    "error": "tool_call missing tool_name",
                }

            return {
                "action": "tool_call",
                "tool_name": tool_name,
                "arguments": arguments if isinstance(arguments, dict) else {},
            }

        elif action == "final_answer":
            answer = obj.get("answer", text).strip()
            if not answer:
                answer = text  # fallback to raw text if answer is empty

            return {
                "action": "final_answer",
                "answer": answer,
            }

        else:
            logger.debug(f"Unknown action: {action}")
            return {
                "action": "malformed",
                "error": f"unknown action: {action}",
            }

    def parse_final_synthesis(self, text: str) -> str:
        """
        Dedicated parsing path for final synthesis turns (e.g. after tool budget exhaustion).

        Preserves pure markdown and plain-text answers directly, while:
        1. Extracting answer field if wrapped in JSON {"action": "final_answer", "answer": "..."}
        2. Extracting answer parameter if wrapped in Hermes XML <invoke name="final_answer">...
        3. Stripping any trailing/leading raw unexecuted tool call syntax (<tool_call> or {"action": "tool_call"}),
           ensuring tool calls are NOT leaked as user answers.
        4. Recovering usable text preceding truncated tool call envelopes or syntax.
        5. Returning empty string if the response contains ONLY an unexecuted tool call or no answer text.
        """
        import re
        import json

        if not text or not text.strip():
            return ""

        raw_trimmed = text.strip()

        # 1. Check if the entire response is a JSON object
        # Try structured JSON parse first
        try:
            parsed_json = json.loads(raw_trimmed)
            if isinstance(parsed_json, dict):
                action = parsed_json.get("action", "").lower()
                if action == "final_answer" and "answer" in parsed_json:
                    return str(parsed_json["answer"]).strip()
                if action == "tool_call" or "tool_name" in parsed_json or action in {
                    "read_file", "search_code", "search_repository", "get_file_outline", "query_rim", "get_tree"
                }:
                    # Response is strictly a tool call JSON with no synthesis text
                    return ""
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. Check for Hermes XML <tool_call> structure
        # If there's an explicit <invoke name="final_answer">, extract the answer parameter
        final_answer_match = re.search(
            r'<invoke\s+name=["\']final_answer["\']>(.*?)</invoke>',
            raw_trimmed,
            re.DOTALL
        )
        if final_answer_match:
            param_match = re.search(
                r'<parameter\s+name=["\']answer["\']>(.*?)</parameter>',
                final_answer_match.group(1),
                re.DOTALL
            )
            if param_match:
                extracted = param_match.group(1).strip()
                if extracted:
                    return extracted

        # 3. Strip any complete <tool_call>...</tool_call> blocks
        cleaned = re.sub(r'<tool_call>.*?</tool_call>', '', raw_trimmed, flags=re.DOTALL)

        # Also strip incomplete/truncated <tool_call> blocks (e.g., `<tool_call>...` until end of string)
        cleaned = re.sub(r'<tool_call>.*$', '', cleaned, flags=re.DOTALL)

        # Strip orphan tags if any remain
        cleaned = re.sub(r'</?tool_call>', '', cleaned)
        cleaned = re.sub(r'<invoke[^>]*>.*?</invoke>', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'<invoke[^>]*>.*$', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'</?invoke[^>]*>', '', cleaned)
        cleaned = re.sub(r'<parameter[^>]*>.*?</parameter>', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'<parameter[^>]*>.*$', '', cleaned, flags=re.DOTALL)
        cleaned = re.sub(r'</?parameter[^>]*>', '', cleaned)

        # 4. Strip JSON tool calls if embedded in text (e.g., text preceding or following {"action": "tool_call", ...})
        for match in re.finditer(r'\{[^{}]*"action"\s*:\s*"(?:tool_call|read_file|search_code|search_repository|get_file_outline|query_rim|get_tree)"[^{}]*\}', cleaned, re.DOTALL):
            cleaned = cleaned.replace(match.group(0), "")

        # Also strip truncated JSON tool calls at the end of the response: e.g., '{"action": "tool_call", ...'
        cleaned = re.sub(r'\{[^{}]*"action"\s*:\s*"(?:tool_call|read_file|search_code|search_repository|get_file_outline|query_rim|get_tree)".*$', '', cleaned, flags=re.DOTALL)

        # Check for embedded JSON final_answer in markdown text: {"action": "final_answer", "answer": "..."}
        fa_json_match = re.search(r'\{[^{}]*"action"\s*:\s*"final_answer"\s*,\s*"answer"\s*:\s*"(.*?)"\s*\}', cleaned, re.DOTALL)
        if fa_json_match:
            try:
                # Parse decoded string value
                extracted_ans = json.loads(f'"{fa_json_match.group(1)}"')
                if extracted_ans.strip():
                    return extracted_ans.strip()
            except Exception:
                pass

        # 5. Normalize whitespace and formatting
        cleaned = re.sub(r'^(\d+\.)\s*\n\s*', r'\1 ', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned).strip()

        return cleaned

