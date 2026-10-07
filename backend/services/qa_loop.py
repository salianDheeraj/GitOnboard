"""
Agentic Q&A loop — shared canonical tool-calling infrastructure for all agents.

Single-turn-at-a-time loop: one LLM call → parse action → execute tool → repeat.
Enforces one tool call per turn (files fetched one-at-a-time), never pre-fetches.
Tracks tool calls, file reads, and RIM metadata access separately.
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

from backend.agent.loop.contracts import AgentLoopConfig, StopReason, ToolObservation
from backend.agent.loop.guardrails import LoopGuardrails
from backend.ai.service import LLMService
from backend.ai.schemas import LLMRequest, Message, MessageRole, Tool
from backend.ai.tokencount.registry import count_full_request
from backend.config import settings
from backend.agent.intent.semantic_query import (
    classify_semantic_query,
    SemanticQueryClass,
    TraversalDirection,
)
from backend.services.qa_protocol import QAProtocolAdapter

if TYPE_CHECKING:
    from backend.logging.structured_logger import StructuredLogger

logger = logging.getLogger(__name__)


def strip_xml_tags(text: str) -> str:
    """Remove XML tags from text, keeping only markdown content."""
    # Remove <tool_call>...</tool_call> wrapper
    text = re.sub(r'<tool_call>|</tool_call>', '', text, flags=re.DOTALL)
    # Remove <invoke name="...">...</invoke> wrapper
    text = re.sub(r'<invoke[^>]*>|</invoke>', '', text, flags=re.DOTALL)
    # Remove <parameter name="...">...</parameter> tags
    text = re.sub(r'<parameter[^>]*>|</parameter>', '', text, flags=re.DOTALL)
    # Fix numbering format: join number on same line as content (e.g., "1.\nText" → "1. Text")
    text = re.sub(r'^(\d+\.)\s*\n\s*', r'\1 ', text, flags=re.MULTILINE)
    # Clean up extra whitespace and normalize paragraph breaks
    text = re.sub(r'\n\s*\n', '\n\n', text).strip()
    return text


def extract_json_answer(text: str) -> str:
    """Extract answer text from JSON-wrapped response."""
    import json

    # Try to parse as JSON and extract answer field
    try:
        # Handle case where response starts with {"action": "final_answer", "answer": "..."}
        data = json.loads(text)
        if isinstance(data, dict) and "answer" in data:
            return str(data["answer"]).strip()
    except (json.JSONDecodeError, ValueError):
        # Not JSON, return as-is
        pass

    return text.strip()


def _tool_specs_to_schema_tools(tool_specs: List[Any]) -> List[Tool]:
    """Convert ToolSpec objects from tool_dispatch to ai.schemas.Tool objects."""
    return [
        Tool(name=spec.name, description=spec.description, parameters=spec.parameters)
        for spec in tool_specs
    ]


@dataclass
class QALoopTurn:
    """Single turn in the loop: one LLM call + optional one tool call."""
    turn_index: int
    tool_call: Optional[Dict[str, Any]] = None  # {"tool_name": ..., "arguments": {...}}
    tool_observation: Optional[Dict[str, Any]] = None
    raw_model_output: str = ""
    prompt_tokens: int = 0  # real, from LLMResponse.usage
    completion_tokens: int = 0  # real, from LLMResponse.usage
    provider: str = ""
    model: str = ""
    duration_ms: float = 0.0


@dataclass
class QALoopResult:
    """Final result from one side of the RIM comparison."""
    answer: str
    stop_reason: StopReason
    turns: List[QALoopTurn] = field(default_factory=list)
    tool_call_count: int = 0
    files_read: List[str] = field(default_factory=list)
    symbols_read: List[str] = field(default_factory=list)
    files_searched: List[str] = field(default_factory=list)  # from search_code/search_repository
    symbols_searched: List[str] = field(default_factory=list)  # from search_repository
    rim_entities_accessed: List[Dict[str, Any]] = field(default_factory=list)  # from query_rim only
    rim_relationship_types_used: List[str] = field(default_factory=list)  # from query_rim only
    latency_ms: Dict[str, float] = field(default_factory=dict)  # {"loop_total", "llm_total", "tool_total"}


@dataclass
class SystemPromptParts:
    """Decomposed system prompt for token accounting."""
    grounding_and_protocol_text: str  # static grounding + protocol instructions
    tool_catalog_text: str  # tool schemas
    rim_metadata_text: str  # RIM metadata block (empty string for baseline)
    full_text: str  # concatenation sent to LLM


class QALoop:
    """
    Agentic Q&A loop: LLM decides what tools to call, executes them one-at-a-time,
    builds answer incrementally. No code-editing semantics, pure question-answering.
    """

    def __init__(
        self,
        llm_service: LLMService,
        tool_dispatch: "ToolDispatchTable",
        config: AgentLoopConfig,
        system_prompt_parts: SystemPromptParts,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        structured_logger: Optional["StructuredLogger"] = None,
        request_id: Optional[str] = None,
        repository: Optional[str] = None,
        mode: Optional[str] = None,  # "baseline" or "rim"
        on_turn: Optional[Callable[["QALoopTurn"], Awaitable[None]]] = None,
    ):
        self.llm_service = llm_service
        self.tool_dispatch = tool_dispatch
        self.config = config
        self.system_prompt_parts = system_prompt_parts
        self.model = model
        self.provider = provider
        self.guardrails = LoopGuardrails(config)
        self.structured_logger = structured_logger
        self.request_id = request_id
        self.repository = repository
        self.mode = mode
        self.on_turn = on_turn
        # Create protocol adapter with model_id for format-specific parsing (Hermes XML for Qwen, JSON for others)
        self.protocol_adapter = QAProtocolAdapter(model_id=model)
        self.consecutive_malformed_count = 0  # Track malformed responses to terminate early
        self.verification_retries = 0  # Track validation rejection count to prevent infinite retry loops
        self.max_verification_retries = 2

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Backward compatibility helper delegating to protocol_adapter."""
        return self.protocol_adapter.parse_response(response_text)

    def _get_provider_budget_profile(self) -> Dict[str, Any]:
        """
        Derive the 4 distinct constraints and safe application budget for the active provider/model:
        - context_window
        - input_tpm
        - single_request_limit
        - application_safety_budget
        """
        model_name = (self.model or "").strip()
        provider = (self.provider or "").strip().lower()

        # 1. Check self.provider if explicitly set
        if not provider:
            # 2. Check active providers attached to llm_service
            active_providers = getattr(self.llm_service, "providers", [])
            if active_providers and hasattr(active_providers[0], "provider_name"):
                provider = active_providers[0].provider_name.lower()

        # 3. If still unknown, infer strictly from model name
        if not provider:
            m_lower = model_name.lower()
            if "gemini" in m_lower:
                provider = "gemini"
            elif "groq" in m_lower or "gpt-oss" in m_lower:
                provider = "groq"
            elif "openrouter" in m_lower or "nemotron" in m_lower:
                provider = "openrouter"
            elif "qwen" in m_lower or "llama" in m_lower:
                provider = "ollama"

        if not provider:
            logger.error(
                f"[QALoop] Provider could not be determined for token budgeting (model='{self.model}', "
                f"llm_service={self.llm_service}). Missing provider information."
            )
            raise ValueError(
                f"[QALoop] Provider information is required for token budgeting but was not provided and could not be determined for model='{self.model}'."
            )

        if provider == "groq":
            context_window = settings.groq_context_window
            input_tpm = settings.groq_input_tpm
            single_request_limit = settings.groq_single_request_limit
            safety_margin = settings.groq_safety_margin_tokens
            control_reservation = settings.groq_control_reservation_tokens
            output_reservation = settings.groq_output_reservation_tokens
        elif provider == "gemini":
            context_window = settings.gemini_context_window
            input_tpm = settings.gemini_input_tpm
            single_request_limit = settings.gemini_single_request_limit
            safety_margin = settings.gemini_safety_margin_tokens
            control_reservation = settings.gemini_control_reservation_tokens
            output_reservation = settings.gemini_output_reservation_tokens
        elif provider == "openrouter":
            context_window = settings.openrouter_context_window
            input_tpm = settings.openrouter_input_tpm
            single_request_limit = settings.openrouter_single_request_limit or 100000
            safety_margin = settings.openrouter_safety_margin_tokens
            control_reservation = settings.openrouter_control_reservation_tokens
            output_reservation = settings.openrouter_output_reservation_tokens
        else:
            # Local / Ollama
            context_window = 32768
            input_tpm = 0
            single_request_limit = 32768
            safety_margin = 1000
            control_reservation = 100
            output_reservation = 2048

        # Calculate safe application budget
        effective_limit = single_request_limit
        if input_tpm and input_tpm > 0:
            effective_limit = min(effective_limit, input_tpm)

        safe_budget = max(
            1000,
            effective_limit - safety_margin - control_reservation - output_reservation
        )

        return {
            "provider": provider,
            "model": self.model or model_name,
            "context_window": context_window,
            "input_tpm": input_tpm,
            "single_request_limit": single_request_limit,
            "safety_margin": safety_margin,
            "control_reservation": control_reservation,
            "output_reservation": output_reservation,
            "safe_budget": safe_budget,
        }

    def _compact_messages_deterministically(self, messages: List[Dict[str, Any]], target_tokens: int) -> List[Dict[str, Any]]:
        """
        Deterministic, rule-based context compaction. ZERO LLM summarization.
        Pass 1: Deduplicate redundant tool reads for the same path.
        Pass 2: Compact older tool observations (>1 turn old) to structural outlines.
        Pass 3: Truncate oversized recent observation bodies.
        """
        if len(messages) <= 1:
            return messages

        user_query_msg = messages[0]
        conversation = list(messages[1:])

        # Pass 1: Deduplicate file reads (keep latest read per file path)
        seen_paths = set()
        for idx in range(len(conversation) - 1, -1, -1):
            msg = conversation[idx]
            content = msg.get("content", "")
            # Identify file read observation or assistant read_file call
            match = re.search(r"read_file\(path=['\"]([^'\"]+)['\"]", content) or re.search(r"lines of ([^\s:]+)", content)
            if match:
                path = match.group(1)
                if path in seen_paths:
                    msg["content"] = f"[Deduplicated older observation for '{path}']"
                else:
                    seen_paths.add(path)

        # Pass 2: Compact older observations (> 2 messages from the end)
        for idx in range(len(conversation) - 2):
            msg = conversation[idx]
            content = msg.get("content", "")
            if "[Deduplicated" in content:
                continue
            if len(content) > 300:
                lines = content.splitlines()
                header = lines[0] if lines else ""
                msg["content"] = f"{header}\n... [Older observation compacted to outline ({len(lines)} lines)] ..."

        # Pass 3: If still heavy, compact non-deduplicated earliest messages
        for idx in range(len(conversation) - 1):
            msg = conversation[idx]
            content = msg.get("content", "")
            if "[Deduplicated" in content:
                continue
            if len(content) > 200:
                msg["content"] = content[:150] + "\n... [Compacted] ..."

        return [user_query_msg] + conversation

    async def run(self, question: str) -> QALoopResult:
        """
        Run the agentic loop: question → LLM → tool dispatch → repeat until done.

        Returns QALoopResult with answer, all turns, metrics, and stop reason.
        """
        loop_start = time.perf_counter()
        llm_total_ms = 0.0
        tool_total_ms = 0.0

        result = QALoopResult(
            answer="",
            stop_reason=StopReason.EXECUTION_TIMEOUT,  # default, overridden below
        )

        # Conversation history: messages appended per turn
        messages: List[Dict[str, Any]] = []

        # Turn 0: add user question
        messages.append({
            "role": "user",
            "content": question,
        })

        print(f"[QALoop:START] Loop starting at T+0ms for question: {question[:60]}...")

        while True:
            turn_index = len(result.turns)
            elapsed = (time.perf_counter() - loop_start) * 1000

            # Log conversation state for context window analysis
            import json as _json
            messages_size = sum(len(m.get("content", "")) for m in messages if isinstance(m, dict))
            messages_size_kb = messages_size / 1024
            print(f"[QALoop:TURN] T+{elapsed:.0f}ms turn_index={turn_index} context_messages={len(messages)} history_size_chars={messages_size} history_size_kb={messages_size_kb:.1f}")

            print(f"[QALoop:TURN] T+{elapsed:.0f}ms turn_index={turn_index} context_messages={len(messages)}")
            self.guardrails.record_turn()

            # 1. Check guardrails BEFORE turn
            stop_reason = self.guardrails.check_pre_turn_limits()
            if stop_reason:
                logger.info(f"[QALoop] Guardrail limit hit: {stop_reason}; forcing final answer")
                result.stop_reason = stop_reason
                # Force a final-answer turn: send current conversation + instruction to answer now
                messages.append({
                    "role": "user",
                    "content": f"[LIMIT REACHED: {stop_reason.value}] You have reached execution limits. Provide your best answer based on what you have gathered so far.",
                })
                # Do one final LLM call (no tools allowed)
                turn = await self._do_final_answer_turn(
                    turn_index, messages, llm_total_ms, tool_total_ms, loop_start
                )
                result.turns.append(turn)
                if self.on_turn:
                    await self.on_turn(turn)
                answer = self.protocol_adapter.parse_final_synthesis(turn.raw_model_output)
                if not answer:
                    answer = turn.raw_model_output
                # Run fact validation on pre-turn limit final answer and append caveats if needed
                _, _, caveated = self._validate_final_answer_against_evidence(answer, result)
                result.answer = caveated
                break

            # 2. Call LLM with current conversation
            logger.debug(f"[QALoop] Turn {turn_index}: calling LLM...")
            turn_start = time.perf_counter()

            try:
                # PROVIDER-AWARE TOKEN BUDGET & CONTEXT MANAGEMENT
                profile = self._get_provider_budget_profile()
                safe_budget = profile["safe_budget"]
                is_rim = self.mode == "rim"
                tool_specs = self.tool_dispatch.specs(include_rim=is_rim)
                schema_tools = _tool_specs_to_schema_tools(tool_specs) if tool_specs else None

                # Build draft request with compact state summary
                sys_text = self.system_prompt_parts.full_text
                if turn_index > 0:
                    state_summary = self.guardrails.state.get_compact_summary()
                    sys_text = f"{sys_text}\n\n{state_summary}"

                llm_messages = [
                    Message(role=MessageRole.SYSTEM, content=sys_text),
                ]
                for msg in messages:
                    try:
                        role_str = msg.get("role", "user").lower() if isinstance(msg, dict) else "user"
                        role = MessageRole(role_str) if role_str in ["system", "user", "assistant", "tool"] else MessageRole.USER
                        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                        tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else None
                        llm_messages.append(Message(role=role, content=content, tool_calls=tool_calls))
                    except Exception as msg_err:
                        logger.error(f"[QALoop] Error processing message: {msg_err}")
                        raise

                request = LLMRequest(
                    messages=llm_messages,
                    model=self.model,
                    temperature=0.2,
                    max_tokens=settings.llm_max_tokens,
                    tools=schema_tools,
                )

                # Preflight check: count complete request tokens
                counted = await count_full_request(request, profile["provider"], profile["model"])
                logger.debug(
                    f"[QALoop] Turn {turn_index}: Preflight count={counted.total_tokens} tokens "
                    f"(method={counted.method}, exact={counted.is_exact}) vs safe_budget={safe_budget}"
                )

                # If request exceeds safe budget, apply deterministic multi-pass compaction
                if counted.total_tokens > safe_budget and len(messages) > 1:
                    logger.warning(
                        f"[QALoop] Turn {turn_index}: Request size ({counted.total_tokens} tokens) "
                        f"exceeds safe budget ({safe_budget} tokens). Running deterministic compaction..."
                    )
                    compacted_messages = self._compact_messages_deterministically(messages, safe_budget)
                    # Rebuild messages
                    llm_messages = [
                        Message(role=MessageRole.SYSTEM, content=self.system_prompt_parts.full_text),
                    ]
                    for msg in compacted_messages:
                        role_str = msg.get("role", "user").lower() if isinstance(msg, dict) else "user"
                        role = MessageRole(role_str) if role_str in ["system", "user", "assistant", "tool"] else MessageRole.USER
                        content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                        tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else None
                        llm_messages.append(Message(role=role, content=content, tool_calls=tool_calls))

                    request = LLMRequest(
                        messages=llm_messages,
                        model=self.model,
                        temperature=0.2,
                        max_tokens=settings.llm_max_tokens,
                        tools=schema_tools,
                    )
                    counted_after = await count_full_request(request, profile["provider"], profile["model"])
                    logger.info(
                        f"[QALoop] Post-compaction request tokens: {counted.total_tokens} -> {counted_after.total_tokens} tokens"
                    )

                llm_response = await self.llm_service.generate(request)
                logger.debug(f"[QALoop] Turn {turn_index}: LLM response ({len(llm_response.content)} chars)")
                self._context_overflow_retries = 0  # Reset retry counter on success
            except Exception as e:
                err_str = str(e).lower()
                is_recoverable_limit = (
                    "exceeds the available context size" in err_str
                    or "exceed_context_size_error" in err_str
                    or "maximum context length" in err_str
                    or "context length exceeded" in err_str
                    or "rate_limit_exceeded" in err_str
                    or "tokens per minute" in err_str
                    or "tpm" in err_str
                    or "request too large" in err_str
                    or "413" in err_str
                    or "resource_exhausted" in err_str
                    or getattr(e, "status_code", None) == 413
                )
                retries = getattr(self, "_context_overflow_retries", 0)
                if is_recoverable_limit and retries < 2:
                    self._context_overflow_retries = retries + 1
                    logger.warning(
                        f"[QALoop] Recoverable provider limit/413 detected at turn {turn_index}. "
                        f"Compacting observations and retrying ({self._context_overflow_retries}/2)..."
                    )
                    # Emergency compaction of conversation history
                    messages = self._compact_messages_deterministically(messages, safe_budget // 2)
                    continue

                logger.error(f"[QALoop] LLM call failed: {e}", exc_info=True)
                result.stop_reason = StopReason.MODEL_ERROR
                result.answer = f"[ERROR] LLM call failed: {str(e)}"

                # Log error if structured logger is available
                if self.structured_logger and self.request_id:
                    self.structured_logger.log_error(
                        stage=f"llm_call_turn_{turn_index}",
                        error=e,
                        context={"mode": self.mode, "turn": turn_index}
                    )
                break

            turn_elapsed = time.perf_counter() - turn_start
            llm_total_ms += turn_elapsed * 1000

            # Log LLM request and response if structured logger is available (after calculating latency)
            if self.structured_logger and self.request_id:
                is_rim = self.mode == "rim"
                user_message = messages[-1].get("content", "") if messages else ""
                tool_specs = self.tool_dispatch.specs(include_rim=is_rim)
                tools_available = [spec.name for spec in tool_specs] if hasattr(tool_specs, '__iter__') else []
                self.structured_logger.log_llm_request(
                    model=self.model or llm_response.model,
                    provider=llm_response.provider,
                    is_rim=is_rim,
                    system_prompt=self.system_prompt_parts.full_text,  # Log full system prompt
                    user_message=user_message,
                    tools_available=tools_available,
                    context_tokens=len(self.system_prompt_parts.full_text) + sum(len(m.get("content", "")) for m in messages)
                )
                self.structured_logger.log_llm_response(
                    response_text=llm_response.content,
                    stop_reason="end_turn",  # LLMResponse doesn't include stop_reason
                    prompt_tokens=llm_response.usage.prompt_tokens,
                    completion_tokens=llm_response.usage.completion_tokens,
                    latency_ms=turn_elapsed * 1000,
                    model=llm_response.model,
                    is_rim=is_rim
                )

            # 3. Parse response: tool_call | final_answer | malformed (using format-specific parser)
            parsed = self.protocol_adapter.parse_response_from_llm_response(llm_response)

            # Log comprehensive turn diagnostics for debugging tool-calling issues
            if self.structured_logger and self.request_id:
                is_rim = self.mode == "rim"
                tool_specs = self.tool_dispatch.specs(include_rim=is_rim)
                available_tools = [spec.name for spec in tool_specs] if hasattr(tool_specs, '__iter__') else []
                protocol_format = "hermes_xml" if self.protocol_adapter.is_qwen else "json"

                self.structured_logger.log_turn_diagnostic(
                    turn_index=turn_index,
                    mode=self.mode,
                    input_query=messages[-1].get("content", "") if messages else None,
                    system_prompt_excerpt=self.system_prompt_parts.grounding_and_protocol_text[:1000],
                    available_tools=available_tools,
                    protocol_format=protocol_format,
                    raw_llm_response=llm_response.content,
                    parsed_action=parsed.get("action"),
                    parsed_tool_name=parsed.get("tool_name"),
                    parsed_arguments=parsed.get("arguments"),
                    parse_error=parsed.get("error"),
                )

            # Log all details to debug for troubleshooting
            elapsed = (time.perf_counter() - loop_start) * 1000
            if parsed["action"] == "tool_call":
                print(f"[QALoop:DECISION] T+{elapsed:.0f}ms turn={turn_index} → tool_call: {parsed.get('tool_name')}")
                logger.debug(f"[QALoop] Turn {turn_index}: tool={parsed.get('tool_name')}")
            elif parsed["action"] == "final_answer":
                print(f"[QALoop:DECISION] T+{elapsed:.0f}ms turn={turn_index} → FINAL_ANSWER")
                logger.debug(f"[QALoop] Turn {turn_index}: FINAL_ANSWER")
            else:
                pass

            turn = QALoopTurn(
                turn_index=turn_index,
                raw_model_output=llm_response.content,
                prompt_tokens=llm_response.usage.prompt_tokens,
                completion_tokens=llm_response.usage.completion_tokens,
                provider=llm_response.provider,
                model=llm_response.model,
                duration_ms=turn_elapsed * 1000,
            )

            # 4. Handle action: tool_call | final_answer | malformed
            if parsed["action"] == "final_answer":
                self.consecutive_malformed_count = 0  # Reset on success
                answer_candidate = parsed.get("answer", llm_response.content)

                # Parse and clean candidate first using dedicated synthesis parser
                parsed_candidate = self.protocol_adapter.parse_final_synthesis(answer_candidate)
                if not parsed_candidate:
                    parsed_candidate = strip_xml_tags(answer_candidate)
                    parsed_candidate = extract_json_answer(parsed_candidate)

                # Stage 4 Fact Validation against tool results in the session
                is_valid, validation_feedback, caveated_answer = self._validate_final_answer_against_evidence(
                    parsed_candidate, result
                )

                if not is_valid:
                    # If verification attempts have not exceeded max retries and turns remain
                    if self.verification_retries < self.max_verification_retries and turn_index < self.config.max_agent_turns:
                        self.verification_retries += 1
                        logger.warning(
                            f"[ValidationGate] Final answer fact validation failed (attempt {self.verification_retries}/{self.max_verification_retries}); prompting correction"
                        )
                        messages.append({
                            "role": "assistant",
                            "content": llm_response.content,
                        })
                        messages.append({
                            "role": "user",
                            "content": validation_feedback or "[VERIFICATION REQUIRED] Your factual claims conflict with repository observations. Please verify or correct them.",
                        })
                        result.turns.append(turn)
                        if self.on_turn:
                            await self.on_turn(turn)
                        continue
                    else:
                        # Max retries reached: attach caveats and complete gracefully
                        logger.warning(
                            f"[ValidationGate] Max verification retries reached ({self.verification_retries}); appending caveats"
                        )
                        result.answer = caveated_answer
                        result.stop_reason = StopReason.COMPLETED_FOR_VERIFICATION
                        result.turns.append(turn)
                        if self.on_turn:
                            await self.on_turn(turn)
                        break

                # Answer passed validation
                result.answer = caveated_answer
                result.stop_reason = StopReason.COMPLETED_FOR_VERIFICATION
                result.turns.append(turn)
                if self.on_turn:
                    await self.on_turn(turn)
                logger.info(f"[QALoop] LLM provided validated final answer at turn {turn_index}")
                break

            elif parsed["action"] == "tool_call":
                self.consecutive_malformed_count = 0  # Reset on success
                # Extract first (and only) tool call from the normalized list
                tool_calls = parsed.get("tool_calls", [])
                if not tool_calls:
                    logger.error(f"[QALoop] tool_call action but no tool_calls in parsed response")
                    continue
                tool_call = tool_calls[0]
                tool_name = tool_call.get("tool_name", "")
                arguments = tool_call.get("arguments", {})

                # 4b. Deterministic Relational Routing:
                # If question has strong relational intent (e.g. who calls, what calls, who imports, what depends on,
                # what inherits, call path, dependency chain) and LLM chooses lexical search (search_repository/search_code)
                # in RIM mode, check if target symbol can be resolved and route to get_code_relationships first.
                if (
                    self.mode == "rim"
                    and tool_name in ("search_repository", "search_code")
                    and getattr(self.tool_dispatch, "target_resolver", None)
                    and getattr(self.tool_dispatch, "graph_traverser", None)
                ):
                    rel_intent = classify_semantic_query(question)
                    strong_rel_classes = (
                        SemanticQueryClass.CALLS_REVERSE,
                        SemanticQueryClass.CALLS_FORWARD,
                        SemanticQueryClass.IMPORTS_REVERSE,
                        SemanticQueryClass.IMPORTS_FORWARD,
                        SemanticQueryClass.INHERITS_REVERSE,
                        SemanticQueryClass.INHERITS_FORWARD,
                        SemanticQueryClass.DATABASE_ACCESS,
                    )
                    if rel_intent.query_class in strong_rel_classes and rel_intent.target_raw_name:
                        resolved_target = self.tool_dispatch.target_resolver.resolve(rel_intent.target_raw_name)
                        # Also check if lexical search argument query itself matches a known symbol
                        lexical_query = str(arguments.get("query", "")).strip()
                        if not resolved_target and lexical_query:
                            resolved_target = self.tool_dispatch.target_resolver.resolve(lexical_query)

                        if resolved_target:
                            # Map semantic query class to relationship_type and direction
                            target_name = getattr(resolved_target, "name", None) or rel_intent.target_raw_name
                            rel_type_map = {
                                SemanticQueryClass.CALLS_REVERSE: ("CALLS", "REVERSE"),
                                SemanticQueryClass.CALLS_FORWARD: ("CALLS", "FORWARD"),
                                SemanticQueryClass.IMPORTS_REVERSE: ("IMPORTS", "REVERSE"),
                                SemanticQueryClass.IMPORTS_FORWARD: ("IMPORTS", "FORWARD"),
                                SemanticQueryClass.INHERITS_REVERSE: ("INHERITS", "REVERSE"),
                                SemanticQueryClass.INHERITS_FORWARD: ("INHERITS", "FORWARD"),
                                SemanticQueryClass.DATABASE_ACCESS: ("DATABASE_ACCESS", "REVERSE"),
                            }
                            mapped_rel, mapped_dir = rel_type_map.get(
                                rel_intent.query_class, ("GENERIC", rel_intent.direction.value)
                            )
                            # Only reroute if get_code_relationships has not already been queried for this target & relationship
                            already_queried = any(
                                t.tool_call
                                and t.tool_call.get("tool_name") in ("get_code_relationships", "query_rim")
                                and str(t.tool_call.get("arguments", {}).get("entity_name", "")).lower() == target_name.lower()
                                and str(t.tool_call.get("arguments", {}).get("relationship_type", "")).upper() == mapped_rel
                                for t in result.turns
                            )
                            if not already_queried:
                                logger.info(
                                    f"[QALoop:RelationalRouting] Strong relational intent detected ({rel_intent.query_class.value}). "
                                    f"Deterministically routing '{tool_name}' -> 'get_code_relationships' for entity '{target_name}'."
                                )
                                print(
                                    f"[QALoop:RELATIONAL_ROUTING] turn={turn_index} rerouting {tool_name} → "
                                    f"get_code_relationships(entity_name={target_name}, relationship_type={mapped_rel}, direction={mapped_dir})"
                                )
                                tool_name = "get_code_relationships"
                                arguments = {
                                    "entity_name": target_name,
                                    "relationship_type": mapped_rel,
                                    "direction": mapped_dir,
                                    "scope": "LOCAL",
                                    "depth": 1,
                                    "limit": 15,
                                }
                                # Update tool_call dict so recording and observations reflect the routed tool
                                tool_call["tool_name"] = tool_name
                                tool_call["arguments"] = arguments

                # 5. Check duplicate tool call in current session with state awareness
                is_sufficient, _ = self.check_evidence_sufficiency(question, result)
                self.guardrails.state.evidence_sufficient = is_sufficient
                is_duplicate, duplicate_feedback = self.guardrails.is_duplicate_call(
                    tool_name, arguments, is_evidence_sufficient=is_sufficient
                )
                if is_duplicate:
                    logger.warning(
                        f"[QALoop] Duplicate tool call detected at turn {turn_index}: {tool_name} with {arguments}"
                    )
                    assistant_message = {
                        "role": "assistant",
                        "content": llm_response.content,
                    }
                    if llm_response.tool_calls:
                        assistant_message["tool_calls"] = [
                            {
                                "type": "function",
                                "id": tc.tool_call_id,
                                "function": {
                                    "name": tc.tool_name,
                                    "arguments": tc.parameters if isinstance(tc.parameters, str) else json.dumps(tc.parameters),
                                },
                            }
                            for tc in llm_response.tool_calls
                        ]
                    messages.append(assistant_message)
                    messages.append({
                        "role": "user",
                        "content": duplicate_feedback,
                    })

                    turn.tool_call = {"tool_name": tool_name, "arguments": arguments}
                    turn.tool_observation = {
                        "tool_name": tool_name,
                        "success": False,
                        "error": {"type": "duplicate_call_prevented", "message": duplicate_feedback},
                        "data": None,
                        "formatted_message": duplicate_feedback,
                    }
                    result.turns.append(turn)
                    if self.on_turn:
                        await self.on_turn(turn)
                    # Do not increment result.tool_call_count because execution was intercepted
                    continue

                # 5b. Evidence-sufficiency stopping gate:
                # If evidence is already sufficient and model still proposes another tool call,
                # immediately transition to final answer synthesis to prevent endless exploration.
                is_sufficient, suff_msg = self.check_evidence_sufficiency(question, result)
                if is_sufficient:
                    logger.info(
                        f"[QALoop] Evidence sufficiency reached at turn {turn_index}; stopping retrieval and transitioning to final answer."
                    )
                    self.guardrails.state.evidence_sufficient = True
                    self.guardrails.state.answer_ready = True
                    messages.append({
                        "role": "assistant",
                        "content": llm_response.content,
                    })
                    messages.append({
                        "role": "user",
                        "content": (
                            f"{suff_msg or '[EVIDENCE SUFFICIENT]'}\n"
                            "You have collected all necessary evidence to answer the question accurately. "
                            "Do not make any further tool calls. Please synthesize and output your final answer now."
                        ),
                    })
                    final_turn = await self._do_final_answer_turn(
                        turn_index + 1, messages, llm_total_ms, tool_total_ms, loop_start
                    )
                    result.turns.append(turn)
                    if self.on_turn:
                        await self.on_turn(turn)
                    result.turns.append(final_turn)
                    if self.on_turn:
                        await self.on_turn(final_turn)
                    answer = self.protocol_adapter.parse_final_synthesis(final_turn.raw_model_output)
                    if not answer:
                        answer = final_turn.raw_model_output
                    _, _, caveated = self._validate_final_answer_against_evidence(answer, result)
                    result.answer = caveated
                    result.stop_reason = StopReason.COMPLETED_FOR_VERIFICATION
                    break

                # 6. Check guardrails on tool call
                stop_reason, should_warn = self.guardrails.record_tool_call(tool_name, arguments)
                if stop_reason:
                    logger.warning(f"[QALoop] Tool call limit hit: {stop_reason}")
                    result.stop_reason = stop_reason
                    # Force final answer
                    messages.append({
                        "role": "assistant",
                        "content": llm_response.content,
                    })
                    messages.append({
                        "role": "user",
                        "content": f"[TOOL LIMIT REACHED] You have reached tool-call limits. Provide your best answer based on what you have gathered.",
                    })
                    final_turn = await self._do_final_answer_turn(
                        turn_index + 1, messages, llm_total_ms, tool_total_ms, loop_start
                    )
                    result.turns.append(turn)
                    if self.on_turn:
                        await self.on_turn(turn)
                    result.turns.append(final_turn)
                    if self.on_turn:
                        await self.on_turn(final_turn)
                    # Parse the final answer response using dedicated synthesis parser
                    answer = self.protocol_adapter.parse_final_synthesis(final_turn.raw_model_output)
                    if not answer:
                        answer = final_turn.raw_model_output
                    # Run fact validation on tool-limit final answer and append caveats if needed
                    _, _, caveated = self._validate_final_answer_against_evidence(answer, result)
                    result.answer = caveated
                    break

                # 7. Execute tool with pre-calculated content token budget
                logger.debug(f"[QALoop] Turn {turn_index}: executing tool '{tool_name}'")
                tool_start = time.perf_counter()
                loop_elapsed = (tool_start - loop_start) * 1000
                print(f"[QALoop:EXEC] T+{loop_elapsed:.0f}ms turn={turn_index} executing {tool_name}")

                # Calculate remaining token budget available for tool output before execution
                profile = self._get_provider_budget_profile()
                control_res = profile.get("control_reservation", 60)
                safe_budget = profile["safe_budget"]
                # Approximate current conversation tokens
                current_chars = len(self.system_prompt_parts.full_text) + sum(len(m.get("content", "")) for m in messages if isinstance(m, dict))
                est_current_tokens = int(current_chars / 3.5)
                remaining_for_tool = max(500, safe_budget - est_current_tokens - control_res)

                try:
                    tool_observation = self.tool_dispatch.dispatch(
                        tool_name,
                        arguments,
                        max_content_tokens=remaining_for_tool,
                        control_reservation_tokens=control_res,
                    )
                except Exception as e:
                    logger.error(f"[QALoop] Tool dispatch error: {e}", exc_info=True)
                    tool_observation = ToolObservation(
                        tool_call_id=f"turn-{turn_index}",
                        tool_name=tool_name,
                        success=False,
                        error={"type": "dispatch_error", "message": str(e)},
                    )

                tool_elapsed = time.perf_counter() - tool_start
                tool_total_ms += tool_elapsed * 1000
                loop_elapsed_after = (time.perf_counter() - loop_start) * 1000
                print(f"[QALoop:RESULT] T+{loop_elapsed_after:.0f}ms turn={turn_index} {tool_name} → success={tool_observation.success} elapsed={tool_elapsed*1000:.0f}ms")

                # Record execution result in guardrails for duplicate detection
                self.guardrails.record_tool_result(
                    tool_name=tool_name,
                    arguments=arguments,
                    success=tool_observation.success,
                    data=tool_observation.data,
                    error=tool_observation.error,
                    turn_index=turn_index,
                )

                # Log tool call if structured logger is available
                if self.structured_logger and self.request_id:
                    is_rim = self.mode == "rim"
                    self.structured_logger.log_tool_call(
                        tool_name=tool_name,
                        arguments=arguments,
                        is_rim=is_rim,
                        turn_number=turn_index,
                        execution_time_ms=tool_elapsed * 1000,
                        success=tool_observation.success,
                        result=tool_observation.data if tool_observation.success else None,
                        error=tool_observation.error.get("message") if tool_observation.error else None
                    )

                # 7. Sanitize observation to prevent context explosion
                sanitized_data = self.guardrails.sanitize_observation(tool_observation.data)

                # Track metadata from tools
                if tool_name == "read_file" and tool_observation.success:
                    path = arguments.get("path", "")
                    if path and path not in result.files_read:
                        result.files_read.append(path)
                elif tool_name == "get_symbol" and tool_observation.success:
                    name = arguments.get("name", "")
                    if name and name not in result.symbols_read:
                        result.symbols_read.append(name)
                elif tool_name == "search_code" and tool_observation.success:
                    # Track files found by search_code
                    data = tool_observation.data or []
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "file" in item:
                                file_path = item["file"]
                                if file_path and file_path not in result.files_searched:
                                    result.files_searched.append(file_path)
                elif tool_name == "search_repository" and tool_observation.success:
                    # Track files and symbols found by search_repository
                    data = tool_observation.data or []
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict):
                                if "file_path" in item:
                                    file_path = item["file_path"]
                                    if file_path and file_path not in result.files_searched:
                                        result.files_searched.append(file_path)
                                if "symbol_name" in item:
                                    symbol_name = item["symbol_name"]
                                    if symbol_name and symbol_name not in result.symbols_searched:
                                        result.symbols_searched.append(symbol_name)
                elif tool_name in ("get_code_relationships", "query_rim") and tool_observation.success:
                    # Track RIM access from get_code_relationships / query_rim tool
                    data = tool_observation.data or {}
                    if data.get("found"):
                        entity_name = arguments.get("entity_name", "")
                        rel_type = arguments.get("relationship_type", "GENERIC")
                        result.rim_entities_accessed.append({
                            "entity_name": entity_name,
                            "relationship_type": rel_type,
                            "direction": arguments.get("direction", "FORWARD"),
                            "related_count": len(data.get("related", [])),
                        })
                        if rel_type not in result.rim_relationship_types_used:
                            result.rim_relationship_types_used.append(rel_type)

                # 8. Append LLM response + tool observation to conversation
                # Preserve native tool_calls from providers (e.g., OpenRouter, Gemini)
                assistant_message = {
                    "role": "assistant",
                    "content": llm_response.content,
                }
                if llm_response.tool_calls:
                    # Include native tool_calls for providers that support them
                    assistant_message["tool_calls"] = [
                        {
                            "type": "function",
                            "id": tc.tool_call_id,
                            "function": {
                                "name": tc.tool_name,
                                "arguments": tc.parameters if isinstance(tc.parameters, str) else json.dumps(tc.parameters),
                            },
                        }
                        for tc in llm_response.tool_calls
                    ]
                messages.append(assistant_message)

                obs_content = self._format_tool_observation(tool_name, tool_observation, sanitized_data)
                is_sufficient, suff_msg = self.check_evidence_sufficiency(question, result)
                if is_sufficient and suff_msg:
                    obs_content += f"\n\n{suff_msg}"

                messages.append({
                    "role": "user",
                    "content": obs_content,
                })

                # Record turn with tool info (include data and formatted message for later reconstruction)
                formatted_message = self._format_tool_observation(tool_name, tool_observation, sanitized_data)

                # Log tool result size for context analysis
                formatted_msg_size = len(formatted_message)
                formatted_msg_kb = formatted_msg_size / 1024
                data_size = len(str(sanitized_data)) if sanitized_data else 0
                print(f"[QALoop:TOOL_RESULT] T+{loop_elapsed_after:.0f}ms turn={turn_index} tool={tool_name} result_chars={formatted_msg_size} result_kb={formatted_msg_kb:.1f} data_chars={data_size}")

                turn.tool_call = {"tool_name": tool_name, "arguments": arguments}
                turn.tool_observation = {
                    "tool_name": tool_name,
                    "success": tool_observation.success,
                    "error": tool_observation.error,
                    "data": sanitized_data,  # Include actual result data for metrics/reconstruction
                    "formatted_message": formatted_message,  # Include formatted message for audit trail
                }
                result.turns.append(turn)
                if self.on_turn:
                    await self.on_turn(turn)
                result.tool_call_count += 1
                logger.debug(f"[QALoop] Turn {turn_index}: {tool_name} executed in {tool_elapsed*1000:.0f}ms")

            else:  # malformed
                self.consecutive_malformed_count += 1

                if self.structured_logger and self.request_id:
                    self.structured_logger.log_malformed_response(
                        raw_content=llm_response.content,
                        parse_error=parsed.get("error", "unknown"),
                        turn_index=turn_index,
                        consecutive_count=self.consecutive_malformed_count,
                        mode=self.mode,
                    )

                # Terminate after 5 consecutive malformed responses
                if self.consecutive_malformed_count >= 5:
                    logger.error(f"[QALoop] TERMINATING: 5 consecutive malformed responses. Model is stuck or out of context.")
                    if self.structured_logger and self.request_id:
                        self.structured_logger.log_malformed_response(
                            raw_content=llm_response.content,
                            parse_error=parsed.get("error", "unknown"),
                            turn_index=turn_index,
                            consecutive_count=self.consecutive_malformed_count,
                            mode=self.mode,
                            terminated=True,
                        )
                    result.answer = "[LOOP TERMINATED] Model produced 5 consecutive malformed responses and could not recover. The model may be stuck or out of context."
                    result.stop_reason = StopReason.MODEL_ERROR
                    result.turns.append(turn)
                    if self.on_turn:
                        await self.on_turn(turn)
                    break

                # Append response and ask LLM to clarify
                messages.append({
                    "role": "assistant",
                    "content": llm_response.content,
                })
                messages.append({
                    "role": "user",
                    "content": "[MALFORMED RESPONSE] Please respond with valid JSON: either {\"action\": \"tool_call\", \"tool_name\": \"...\", \"arguments\": {...}} or {\"action\": \"final_answer\", \"answer\": \"...\"}",
                })
                result.turns.append(turn)
                if self.on_turn:
                    await self.on_turn(turn)

        # Calculate latencies
        loop_elapsed = time.perf_counter() - loop_start
        result.latency_ms = {
            "loop_total": loop_elapsed * 1000,
            "llm_total": llm_total_ms,
            "tool_total": tool_total_ms,
        }

        # Log completion - show critical summary
        total_elapsed = (time.perf_counter() - loop_start) * 1000
        log_message = (f"[QALoop] Completed {len(result.turns)} turns | "
                      f"{result.tool_call_count} tool calls | "
                      f"{result.stop_reason} | "
                      f"Total time: {total_elapsed:.0f}ms")

        print(f"[QALoop:END] T+{total_elapsed:.0f}ms turns={len(result.turns)} tools={result.tool_call_count} reason={result.stop_reason.value}")

        if result.tool_call_count == 0:
            logger.error(f"{log_message} | ❌ ERROR: No tools called - malformed JSON or protocol failure")
        else:
            logger.info(log_message)

        return result

    async def _do_final_answer_turn(
        self, turn_index: int, messages: List[Dict[str, Any]],
        llm_total_ms: float, tool_total_ms: float, loop_start: float
    ) -> QALoopTurn:
        """Execute one final LLM call (no tools) to generate answer."""
        turn_start = time.perf_counter()

        try:
            # Build dedicated synthesis system prompt (do not send the tool-calling prompt!)
            final_system_prompt = (
                "You are an expert repository analysis assistant. "
                "The exploration phase is complete. Based strictly on the conversation history "
                "and tool observations above, provide a comprehensive, clear, and well-structured Markdown "
                "answer to the user's initial question. Do NOT attempt to call any tools or output tool syntax. "
                "Provide only your final answer in Markdown directly."
            )
            llm_messages = [
                Message(role=MessageRole.SYSTEM, content=final_system_prompt),
            ]

            # Context windowing: keep initial query and recent turns to prevent token explosion on rate-limited providers
            window_size = 10
            msgs_to_include = messages
            if len(messages) > window_size and len(messages) > 1:
                msgs_to_include = [messages[0]] + messages[-(window_size - 1):]

            for msg in msgs_to_include:
                try:
                    role_str = msg.get("role", "user").lower() if isinstance(msg, dict) else "user"
                    role = MessageRole(role_str) if role_str in ["system", "user", "assistant", "tool"] else MessageRole.USER
                    content = msg.get("content", "") if isinstance(msg, dict) else str(msg)
                    # If content is a tool observation, truncate if excessively long (>3000 chars)
                    if role == MessageRole.TOOL or "[read_file]" in content or "[search" in content:
                        if len(content) > 3000:
                            content = content[:3000] + "\n...[truncated for synthesis]..."
                    llm_messages.append(Message(role=role, content=content))
                except Exception as msg_err:
                    logger.error(f"[QALoop] Error processing message in final answer turn: {msg_err}")
                    raise

            # Add explicit instruction for final synthesis
            llm_messages.append(
                Message(
                    role=MessageRole.USER,
                    content=(
                        "Please provide your complete, final answer in Markdown now based on all the findings "
                        "and evidence gathered above. Do not call any tools."
                    ),
                )
            )

            request = LLMRequest(
                messages=llm_messages,
                model=self.model,
                temperature=0.2,
                max_tokens=settings.llm_max_tokens,
            )
            llm_response = await self.llm_service.generate(request)

            raw_output = (llm_response.content or "").strip()
            # Parse final answer using dedicated synthesis parser
            parsed_answer = self.protocol_adapter.parse_final_synthesis(raw_output)

            # If model returned no content or returned only unexecuted tool calls in final turn, synthesize fallback from observations
            if not parsed_answer:
                logger.warning("[QALoop] Final turn produced no usable answer text; synthesizing summary from observations")
                obs_snippets = []
                for m in reversed(messages):
                    content = m.get("content", "") if isinstance(m, dict) else ""
                    if any(k in content for k in ["[read_file]", "[search", "routes", "export", "class ", "def "]):
                        lines = [line for line in content.splitlines() if line.strip() and not line.startswith("[")]
                        if lines:
                            obs_snippets.append("\n".join(lines[:12]))
                    if len(obs_snippets) >= 3:
                        break
                if obs_snippets:
                    raw_output = (
                        "### Key Repository Findings\n\n"
                        + "\n\n---\n\n".join(reversed(obs_snippets))
                    )
                else:
                    raw_output = "The repository analysis finished. Please review the collected evidence in the session."
            else:
                raw_output = parsed_answer

        except Exception as e:
            logger.error(f"[QALoop] Final answer LLM call failed: {e}", exc_info=True)
            return QALoopTurn(
                turn_index=turn_index,
                raw_model_output=f"[ERROR] Failed to generate answer: {str(e)}",
                prompt_tokens=0,
                completion_tokens=0,
                provider="error",
                model="error",
                duration_ms=(time.perf_counter() - turn_start) * 1000,
            )

        return QALoopTurn(
            turn_index=turn_index,
            raw_model_output=raw_output,
            prompt_tokens=llm_response.usage.prompt_tokens if llm_response.usage else 0,
            completion_tokens=llm_response.usage.completion_tokens if llm_response.usage else 0,
            provider=llm_response.provider,
            model=llm_response.model,
            duration_ms=(time.perf_counter() - turn_start) * 1000,
        )

    def _has_retrieval_been_performed(self, result: QALoopResult) -> bool:
        """
        Check if any repository retrieval has been performed in this execution.

        Verification-gate enforcement: absence claims require actual retrieval evidence.

        Returns True if: search_repository, read_file, or get_symbol was called and succeeded.
        """
        retrieval_tools = ["search_repository", "read_file", "get_symbol", "search_code", "get_code_relationships", "query_rim"]

        for turn in result.turns:
            if turn.tool_call:
                tool_name = turn.tool_call.get("tool_name", "")
                if tool_name in retrieval_tools:
                    # Check if tool call succeeded
                    if turn.tool_observation and turn.tool_observation.get("success", False):
                        return True

        return False

    def check_evidence_sufficiency(self, question: str, result: QALoopResult) -> Tuple[bool, Optional[str]]:
        """
        Evaluate whether the evidence collected so far is sufficient to answer the user's question,
        enabling proactive early stopping and synthesis rather than exhausting execution turns.

        Returns:
            Tuple[is_sufficient, recommendation_message]
        """
        if not question or not result or len(result.turns) == 0:
            return False, None

        q_lower = question.lower()
        successful_reads = [
            t for t in result.turns
            if t.tool_call and t.tool_call.get("tool_name") == "read_file"
            and t.tool_observation and t.tool_observation.get("success")
            and isinstance(t.tool_observation.get("data"), dict)
            and len(str(t.tool_observation.get("data", {}).get("raw_text") or t.tool_observation.get("data", {}).get("content") or "")) > 40
        ]
        successful_graph = [
            t for t in result.turns
            if t.tool_call and t.tool_call.get("tool_name") in ("get_code_relationships", "query_rim")
            and t.tool_observation and t.tool_observation.get("success")
            and isinstance(t.tool_observation.get("data"), dict)
            and t.tool_observation.get("data", {}).get("found")
        ]

        # Scenario 1: Relational question (caller / callee / imports) where get_code_relationships found relationship
        is_relational_q = any(w in q_lower for w in ["who calls", "what calls", "caller", "callee", "depend", "import", "where is", "inherits", "what does"])
        if is_relational_q and len(successful_graph) >= 1:
            # If the graph found static confirmed callees/callers, we have sufficient evidence
            # (either with or without subsequent read_file)
            if len(successful_reads) >= 1:
                return True, (
                    "[EVIDENCE SUFFICIENT] Structural relationship and relevant code implementation have been inspected. "
                    "You have sufficient evidence to provide your final answer now. Do not call additional tools."
                )
            # If graph has confirmed edges and question just asks who/what calls
            first_graph = successful_graph[0].tool_observation.get("data", {})
            if first_graph.get("resolution") == "STATIC_CONFIRMED" and len(first_graph.get("related", [])) > 0:
                return True, (
                    "[EVIDENCE SUFFICIENT] Structural relationships have been confirmed by code graph analysis. "
                    "You have sufficient evidence to provide your final answer now. Do not call additional tools."
                )

        # Scenario 2: Functional question ("what does X do", "how does X work") where the target function/file has been read
        is_functional_q = any(w in q_lower for w in ["what does", "how does", "explain", "how is", "where is", "definition of"])
        if is_functional_q and len(successful_reads) >= 1:
            return True, (
                "[EVIDENCE SUFFICIENT] The target implementation has been inspected with read_file. "
                "You have sufficient evidence to provide your final answer now. Do not call additional tools."
            )

        return False, None

    def _retrieval_evidence_supports_absence(self, result: QALoopResult, answer: str = "") -> Tuple[bool, str]:
        """
        Check if the actual retrieval result data supports an absence claim.

        Stage 4 Rules:
        - Do not treat a failed search, empty result from a narrow search, partial read,
          or incomplete search scope as proof that something does not exist.
        - Absence of evidence is not evidence of absence.
        - Returns (is_supported, explanation)

        Returns (True, "supported") only if:
        - Retrieval tools were executed and succeeded.
        - AND no positive evidence of the claimed entity was discovered.
        - AND searches were not failed calls or error responses.
        - If a search was executed with query 'Q' and returned 0 matches, that can support
          absence of 'Q' iff no other tool found 'Q' and the call was successful.
        """
        retrieval_tools = ["search_repository", "read_file", "get_symbol", "search_code", "get_code_relationships", "query_rim"]
        found_positive_matches: List[str] = []
        had_successful_retrieval = False
        had_failed_search = False

        answer_lower = answer.lower() if answer else ""

        for turn in result.turns:
            if not turn.tool_call or not turn.tool_observation:
                continue

            tool_name = turn.tool_call.get("tool_name", "")
            if tool_name not in retrieval_tools:
                continue

            # Check if retrieval succeeded
            if not turn.tool_observation.get("success", False):
                had_failed_search = True
                continue

            had_successful_retrieval = True
            result_data = turn.tool_observation.get("data", None)

            # Analyze result based on tool type
            if tool_name in ("search_repository", "search_code"):
                if isinstance(result_data, list) and len(result_data) > 0:
                    for item in result_data:
                        if isinstance(item, dict):
                            sym = item.get("symbol") or ""
                            file_p = item.get("file") or item.get("path") or ""
                            snip = item.get("snippet") or ""
                            # If answer claims this entity does not exist, but we found it
                            found_positive_matches.append(f"{sym} in {file_p}: {snip[:80]}".strip())

            elif tool_name == "get_symbol":
                if result_data:
                    if isinstance(result_data, list):
                        for sym in result_data:
                            if isinstance(sym, dict):
                                found_positive_matches.append(f"symbol {sym.get('name')} in {sym.get('file')}")
                    elif isinstance(result_data, dict):
                        found_positive_matches.append(f"symbol {result_data.get('name')}")

            elif tool_name == "read_file":
                if isinstance(result_data, dict):
                    raw_text = result_data.get("raw_text") or result_data.get("content") or ""
                    file_p = result_data.get("path", "")
                    if raw_text:
                        # File exists and has content
                        found_positive_matches.append(f"file content in {file_p}")

        if not had_successful_retrieval:
            if had_failed_search:
                return False, "Failed or errored searches cannot be treated as proof of absence."
            return False, "No retrieval was performed to verify this absence claim."

        # Expanded dictionary of common architectural entities and their related keywords/aliases
        suspicious_terms = [
            ("postgres", ["postgres", "postgresql", "psycopg"]),
            ("postgresql", ["postgres", "postgresql", "psycopg"]),
            ("mysql", ["mysql", "pymysql"]),
            ("sqlite", ["sqlite", "sqlite3"]),
            ("redis", ["redis"]),
            ("chroma", ["chroma", "chromadb"]),
            ("qdrant", ["qdrant"]),
            ("jwt", ["jwt", "pyjwt"]),
            ("token", ["token", "tokens"]),
            ("auth", ["auth", "authenticate", "authoriz"]),
            ("session", ["session"]),
            ("docker", ["docker", "dockerfile"]),
            ("fastapi", ["fastapi"]),
            ("router", ["router", "routing"]),
            ("endpoint", ["endpoint", "endpoints"]),
            ("celery", ["celery"]),
            ("worker", ["worker"]),
            ("queue", ["queue"]),
            ("cache", ["cache"]),
            ("blob", ["blob"]),
            ("s3", ["s3", "boto3"]),
            ("azure", ["azure"]),
            ("websocket", ["websocket", "websockets", "ws"]),
            ("cors", ["cors"]),
            ("middleware", ["middleware"]),
            ("graphql", ["graphql", "strawberry", "ariadne"]),
            ("oauth", ["oauth", "oauth2"]),
            ("migration", ["migration", "migrations", "alembic"]),
            ("alembic", ["alembic"]),
            ("prisma", ["prisma"]),
        ]

        # 1. Contradiction Check: If positive evidence was retrieved that contradicts an absence claim
        if found_positive_matches and answer_lower:
            for term, aliases in suspicious_terms:
                if term in answer_lower and any(neg in answer_lower for neg in ["no ", "not ", "does not", "doesn't", "without"]):
                    # Model claims absence of term - did positive observations contain it?
                    for turn in result.turns:
                        obs = turn.tool_observation or {}
                        if obs.get("success"):
                            data_str = str(obs.get("data", "")).lower()
                            if any(alias in data_str for alias in aliases):
                                return False, f"Contradicted by evidence: repository search/read observed '{term}' in the codebase."

        # 2. Targeted Query Relevance Check:
        # Absence claims must be backed by searches relevant to the entity being claimed absent.
        # An empty result from searching an unrelated term (e.g. search("foo") -> 0) does NOT justify claiming "Redis is absent".
        if answer_lower:
            # Find all suspicious terms that appear in negative context in the answer
            claimed_absent = []
            for term, aliases in suspicious_terms:
                if term in answer_lower and any(neg in answer_lower for neg in ["no ", "not ", "does not", "doesn't", "without"]):
                    claimed_absent.append((term, aliases))

            if claimed_absent:
                # Check whether ANY executed retrieval tool searched for ANY of the claimed absent entities/aliases
                # If specific architectural terms (e.g., redis, postgres, celery) are claimed absent,
                # but searches only targeted unrelated terms (e.g., "foo", "hello"), reject the absence claim.
                searched_queries = []
                for turn in result.turns:
                    tc = turn.tool_call or {}
                    obs = turn.tool_observation or {}
                    if not obs.get("success"):
                        continue
                    args = tc.get("arguments", {})
                    q_str = str(args.get("query") or args.get("name") or args.get("entity_name") or args.get("path") or "").lower()
                    if q_str:
                        searched_queries.append(q_str)

                # Check for primary claimed entity:
                # If answer claims "no Redis cache", and query was "redis", that matches!
                has_relevant_search = False
                for term, aliases in claimed_absent:
                    for q in searched_queries:
                        if any(alias in q for alias in aliases) or q in aliases or term in q:
                            has_relevant_search = True
                            break
                    if has_relevant_search:
                        break

                if not has_relevant_search:
                    terms_str = ", ".join(t[0] for t in claimed_absent[:3])
                    return False, f"Absence claim for '{terms_str}' is unverified: searches performed in this session did not target '{terms_str}' or related identifiers."

        return True, "supported"

    def _is_absence_claim(self, answer: str) -> bool:
        """
        Improved heuristic: detect if answer claims repository-wide absence.

        Handles multiple formulations:
        - Direct negation: "does not X", "there is no X"
        - Soft negation: "doesn't appear", "seems not to"
        - Search-qualified: "found no X", "no results"
        - Question-response: "Is there X?" answered with "No"
        """
        answer_lower = answer.lower()

        # Direct negation patterns (primary)
        direct_negation = [
            "does not",
            "doesn't",
            "do not",
            "don't",
            "is not",
            "isn't",
            "was not",
            "wasn't",
            "are not",
            "aren't",
            "no function",
            "no module",
            "no package",
            "no component",
            "no service",
            "no feature",
            "no implementation",
            "no code",
            "no database",
            "no postgres",
            "no redis",
            "no auth",
            "no model",
            "no class",
            "there is no",
            "there are no",
            "there's no",
            "has no ",
            "have no ",
            "contains no ",
        ]

        # Soft/qualified negation (secondary)
        soft_negation = [
            "does not appear",
            "doesn't appear",
            "appears not",
            "appears to not",
            "doesn't seem",
            "does not seem",
            "seems not",
            "unable to find",
            "cannot find",
            "could not find",
            "couldn't find",
            "found no",
            "no evidence",
            "no mention",
            "no instances",
            "no references",
            "not found",
            "not present",
            "not implemented",
            "not detected",
            "no results",
        ]

        # Entity context (broadened)
        entity_context = [
            "function",
            "module",
            "package",
            "library",
            "component",
            "service",
            "feature",
            "class",
            "interface",
            "method",
            "implementation",
            "pattern",
            "dependency",
            "tool",
            "framework",
            "redis",
            "database",
            "cache",
            "authentication",
            "reset",
            "recovery",
        ]

        repo_context = [
            "repository",
            "codebase",
            "project",
            "code",
            "repo",
            "repository",
            "this repo",
            "this project",
        ]

        # Strategy: Detect absence if:
        # 1. Direct negation is present
        # 2. OR soft negation + entity/repo context
        # This catches most natural absence formulations

        has_direct = any(p in answer_lower for p in direct_negation)

        has_soft = any(p in answer_lower for p in soft_negation)
        has_context = (
            any(e in answer_lower for e in entity_context) or
            any(r in answer_lower for r in repo_context)
        )

        return has_direct or (has_soft and has_context)

    def _validate_final_answer_against_evidence(
        self, answer: str, result: QALoopResult
    ) -> Tuple[bool, Optional[str], str]:
        """
        Stage 4: Validate factual claims in the final answer against tool results
        available in the current QA session.

        Distinguishes:
        - Supported claims (passes validation)
        - Contradicted claims (evidence directly disproves the claim)
        - Insufficient / inconclusive claims (absence of evidence, failed search, truncated reads)

        Returns:
            Tuple[is_valid, prompt_feedback, sanitized_or_caveated_answer]:
            - is_valid (bool): True if answer is verified or acceptable. False if contradicted or unjustified absence claim.
            - prompt_feedback (Optional[str]): Guidance sent to LLM for investigation/correction if retrying.
            - sanitized_or_caveated_answer (str): The answer with appropriate caveats or corrections when retries exhausted.
        """
        if not answer or not answer.strip():
            return False, "Final answer is empty. Please provide your answer based on repository evidence.", answer

        answer_clean = answer.strip()
        contradictions: List[str] = []
        caveats: List[str] = []

        # 1. Check for absence claims
        if self._is_absence_claim(answer_clean):
            is_supported, reason = self._retrieval_evidence_supports_absence(result, answer_clean)
            if not is_supported:
                contradictions.append(f"Absence claim unverified: {reason}")

        # 2. Check for contradictions with read_file contents
        # Extract files inspected during the session
        inspected_files: Dict[str, Dict[str, Any]] = {}
        for turn in result.turns:
            tc = turn.tool_call or {}
            obs = turn.tool_observation or {}
            if tc.get("tool_name") == "read_file" and obs.get("success") and isinstance(obs.get("data"), dict):
                p = tc.get("arguments", {}).get("path", "")
                if p:
                    inspected_files[p] = obs["data"]

        # Check for claims about specific file existence or non-existence
        for turn in result.turns:
            tc = turn.tool_call or {}
            obs = turn.tool_observation or {}
            if tc.get("tool_name") == "read_file":
                p = tc.get("arguments", {}).get("path", "")
                if not obs.get("success") or (isinstance(obs.get("data"), dict) and obs.get("data", {}).get("error") == "wrong_path"):
                    # File was not found at this exact path
                    # If answer confidently claims the file definitely exists at this path:
                    pass

        # Check for truncated read caveats:
        # If the answer makes definitive claims about a file that was truncated, note potential incompleteness
        truncated_files = [p for p, data in inspected_files.items() if data.get("is_truncated") or data.get("_truncated")]
        if truncated_files:
            # If the user answer makes sweeping completeness claims about this file
            for tf in truncated_files:
                base_name = tf.split("/")[-1]
                if base_name in answer_clean and ("entire" in answer_clean.lower() or "only" in answer_clean.lower() or "complete" in answer_clean.lower()):
                    caveats.append(f"Note: '{tf}' was partially read due to line limits. Further definitions may exist beyond the inspected lines.")

        # Check for contradictions with specific search results and inspected file contents
        for turn in result.turns:
            tc = turn.tool_call or {}
            obs = turn.tool_observation or {}
            tname = tc.get("tool_name", "")
            if not obs.get("success"):
                continue
            data = obs.get("data")

            # Check if answer claims a symbol doesn't exist when search_repository found it
            if tname in ("search_repository", "search_code", "get_symbol") and isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        sym_name = item.get("symbol") or item.get("name")
                        file_name = item.get("file") or item.get("path")
                        if sym_name and len(sym_name) > 2:
                            # If answer specifically says sym_name does not exist / isn't present
                            sym_pat = re.compile(rf"\b(no|not|does not contain|does not exist|cannot find|isn't any)\b[^\.\n]*\b{re.escape(sym_name)}\b", re.IGNORECASE)
                            if sym_pat.search(answer_clean):
                                contradictions.append(f"Claim that '{sym_name}' does not exist is contradicted by tool observation in {file_name}.")

            # Also check if answer claims a symbol/class doesn't exist when read_file returned it
            elif tname == "read_file" and isinstance(data, dict):
                file_text = data.get("raw_text") or data.get("content") or ""
                file_name = data.get("path", "")
                # Extract classes and functions defined in file
                for def_match in re.finditer(r"\b(?:class|def|function|interface)\s+([A-Za-z0-9_]+)", file_text):
                    sym_name = def_match.group(1)
                    if len(sym_name) > 2:
                        sym_pat = re.compile(rf"\b(no|not|does not contain|does not exist|cannot find|isn't any)\b[^\.\n]*\b{re.escape(sym_name)}\b", re.IGNORECASE)
                        if sym_pat.search(answer_clean):
                            contradictions.append(f"Claim that '{sym_name}' does not exist is contradicted by tool observation in {file_name}.")

        if contradictions:
            feedback_msg = (
                "[VERIFICATION FAILED] The following factual claims conflict with tool observations or lack evidence:\n"
                + "\n".join(f"- {c}" for c in contradictions)
                + "\n\nPlease review your observations, correct any contradicted statements, and provide a verified answer."
            )
            # Caveated answer for when retries are exhausted
            warning_box = (
                "\n\n> [!WARNING]\n> **Verification Caveat:**\n"
                + "\n".join(f"> - {c}" for c in contradictions)
            )
            caveated_answer = answer_clean + warning_box
            return False, feedback_msg, caveated_answer

        # No direct contradictions; append minor truncation caveats if applicable
        if caveats:
            disclaimer = "\n\n> [!NOTE]\n" + "\n".join(f"> {c}" for c in caveats)
            return True, None, answer_clean + disclaimer

        return True, None, answer_clean

    def _verify_absence_claim(self, answer: str, result: QALoopResult) -> bool:
        """
        Enforcement gate: absence claims must be backed by actual retrieval evidence.

        Preserves existing API contract for backward compatibility.
        Delegates to _retrieval_evidence_supports_absence.
        """
        if not self._is_absence_claim(answer):
            return True

        supported, _ = self._retrieval_evidence_supports_absence(result, answer)
        if not supported:
            logger.warning(f"[VerificationGate] Absence claim without supporting retrieval evidence: {answer[:100]}...")
            return False
        return True

    def _format_tool_observation(
        self, tool_name: str, observation: ToolObservation, data: Any
    ) -> str:
        """Format tool observation for appending to conversation.

        Includes both summary and actual data so LLM can reason over results.
        """
        if not observation.success:
            error = observation.error or {}
            return f"[TOOL ERROR] {tool_name}: {error.get('message', 'unknown error')}"

        # Format with summary + actual data so LLM can use the results
        if tool_name == "read_file" and isinstance(data, dict):
            # Check if data was truncated by sanitization
            if data.get("_truncated"):
                path = data.get('path', 'unknown file')
                return (
                    f"[read_file] FILE TOO LARGE: {path} exceeds size limit.\n\n"
                    f"SOLUTION: Use one of these approaches:\n"
                    f"1. search_repository: Find specific functions/classes in the file\n"
                    f"   Example: search_repository with query 'function_name' or 'class_name'\n"
                    f"2. read_file with line range: Read specific sections\n"
                    f"   Example: read_file('{path}', start_line=50, end_line=150)\n"
                    f"3. get_symbol: Find definitions of specific symbols\n"
                    f"   Example: get_symbol('MyClass') or get_symbol('my_function')\n\n"
                    f"These tools will help you locate and read relevant parts without loading the entire file."
                )

            path = data.get('path', '')
            start_line = data.get('start_line', 1)
            end_line = data.get('end_line')  # Don't default to 0 - let it be None if missing
            total_lines = data.get('total_lines', 0)
            content = data.get('content', '')
            raw_text = data.get('raw_text', '')

            # Use formatted content (which contains line numbers and context protection notice) if available,
            # otherwise fall back to raw_text
            actual_content = content or raw_text

            # If end_line is missing, use total_lines
            if end_line is None:
                end_line = total_lines or start_line

            summary = f"[read_file] {path} lines {start_line}-{end_line}: {len(actual_content)} chars (total: {total_lines})\n"
            if actual_content:
                return summary + actual_content
            return summary
        elif tool_name in ("get_code_relationships", "query_rim") and isinstance(data, dict):
            display_name = tool_name
            if not data.get("found"):
                resolution = data.get("resolution", "")
                msg = data.get("message", "")
                fallback = data.get("fallback")
                fb_str = f" Suggested next step: call {fallback['tool']}(query='{fallback['query']}')" if fallback else ""
                if resolution == "NO_STATIC_EDGE_FOUND":
                    return f"[{display_name}] No static edge found: {msg}.{fb_str}"
                return f"[{display_name}] Entity not found: {msg}.{fb_str}"

            related = data.get("related", [])
            target_info = ""
            target_loc = ""
            target_line = 1
            if "target" in data and isinstance(data["target"], dict):
                t = data["target"]
                target_loc = t.get("location", "")
                target_line = t.get("line", 1) or 1
                target_info = f" for '{t.get('name', '')}' ({t.get('type', '')} at {target_loc}:{target_line})"

            summary = f"[{display_name}] Found {len(related)} related entities{target_info}:\n"
            inspection_recommendations = []

            # Guide to inspect the caller/target implementation itself if known
            if target_loc and target_loc not in ("?", ""):
                try:
                    t_ln = int(target_line)
                    start_w = max(1, t_ln - 5)
                    end_w = t_ln + 50
                    inspection_recommendations.append(
                        f"read_file(path='{target_loc}', start_line={start_w}, end_line={end_w}) to inspect caller implementation"
                    )
                except (ValueError, TypeError):
                    pass

            for entity in related:
                name = entity.get("name", "?")
                entity_type = entity.get("entity_type", "?")
                location = entity.get("location", "?")
                line_num = entity.get("line_number", "?")
                role = entity.get("relationship_role", "?")
                path_str = f", path: {' -> '.join(entity['path'])}" if entity.get("path") else ""
                summary += f"  - {name} ({entity_type}, {location}:{line_num}, role: {role}{path_str})\n"

                # If entity has a valid file path and line number, suggest targeted code inspection
                if location and location not in ("?", "") and line_num not in ("?", None, ""):
                    try:
                        ln = int(line_num)
                        start_win = max(1, ln - 15)
                        end_win = ln + 25
                        if len(inspection_recommendations) < 3:
                            inspection_recommendations.append(
                                f"read_file(path='{location}', start_line={start_win}, end_line={end_win}) to inspect '{name}'"
                            )
                    except (ValueError, TypeError):
                        pass

            if inspection_recommendations:
                summary += "\nActionable next step for verification:\n"
                for rec in inspection_recommendations:
                    summary += f"- Call {rec}\n"

            return summary
        elif tool_name == "search_repository" and isinstance(data, list):
            summary = f"[search_repository] Found {len(data)} results:\n"
            for result in data[:10]:  # Include first 10 results
                if isinstance(result, dict):
                    file_path = result.get("file", result.get("path", "?"))
                    result_type = result.get("type", "")
                    # For symbol/code results, include additional context
                    if result_type == "symbol" and "symbol" in result:
                        summary += f"  - {file_path}: {result['symbol']} (lines {result.get('lines', '?')})\n"
                    elif result_type == "code" and "line" in result:
                        snippet = result.get("snippet", "")[:50]
                        summary += f"  - {file_path}:{result['line']} {snippet}\n"
                    else:
                        summary += f"  - {file_path}\n"
                else:
                    summary += f"  - {str(result)[:50]}\n"
            if len(data) > 10:
                summary += f"  ... and {len(data) - 10} more results available.\n"
                summary += f"To fetch more: search_repository(query=..., limit=10, offset={len(data[:10])})\n"
            return summary
        elif tool_name == "get_symbol" and isinstance(data, list):
            summary = f"[get_symbol] Found {len(data)} symbols:\n"
            for symbol in data[:10]:  # Include first 10 symbols
                name = symbol.get("name", "?") if isinstance(symbol, dict) else str(symbol)[:50]
                summary += f"  - {name}\n"
            if len(data) > 10:
                summary += f"  ... and {len(data) - 10} more symbols\n"
            return summary
        elif tool_name == "get_tree" and isinstance(data, dict):
            # Special handling for tree output - preserve Unicode box drawing characters
            tree = data.get("tree", "")
            file_count = data.get("file_count", 0)
            path = data.get("path", "/")
            summary = f"[get_tree] {path} ({file_count} files):\n"
            return summary + tree
        else:
            # Generic summary with actual data included
            import json
            try:
                if isinstance(data, (dict, list)):
                    data_str = json.dumps(data, default=str)[:500]
                else:
                    data_str = str(data)[:500]
            except:
                data_str = str(data)[:500]
            return f"[{tool_name}] Result: {data_str}"
