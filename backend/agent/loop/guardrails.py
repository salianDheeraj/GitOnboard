"""
Phase 6 Guardrails & Execution Limits for Engineering Agent Loop.

Enforces:
  - Max agent turns
  - Max total tool calls
  - Max command/terminal executions
  - Overall task execution timeout
  - Observation payload truncation
  - Repeated tool call loop detection via normalized signature hashing
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from backend.agent.loop.contracts import AgentLoopConfig, StopReason

logger = logging.getLogger(__name__)

# Known terminal / command execution tools
COMMAND_TOOL_NAMES = {
    "execute_command",
    "sandbox_bash",
    "run_terminal_command",
    "run_tests",
    "run_build",
}


class LoopGuardrails:
    """
    Stateful execution monitor enforcing hard safety limits and loop detection.
    """

    def __init__(self, config: Optional[AgentLoopConfig] = None):
        self.config = config or AgentLoopConfig()
        self.turn_count = 0
        self.tool_call_count = 0
        self.command_count = 0
        self.start_time = time.perf_counter()
        self.recent_signatures: List[str] = []
        # Session-wide history tracking: sig -> dict with call count, last_success, last_data, error
        self.executed_tools: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def normalize_arguments(arguments: Any) -> str:
        """
        Recursively normalize arguments into a canonical JSON string
        independent of key ordering or dictionary implementation.
        """
        import json

        def _sort_obj(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: _sort_obj(v) for k, v in sorted(obj.items())}
            elif isinstance(obj, list):
                return [_sort_obj(item) for item in obj]
            return obj

        try:
            sorted_obj = _sort_obj(arguments)
            return json.dumps(sorted_obj, sort_keys=True, separators=(',', ':'), default=str)
        except Exception:
            return str(sorted(arguments.items())) if isinstance(arguments, dict) else str(arguments)

    def get_tool_signature(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Returns the canonical normalized signature for a tool invocation."""
        norm_args = self.normalize_arguments(arguments)
        return f"{tool_name}:{norm_args}"

    def is_duplicate_call(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Checks if the tool call with identical normalized arguments has already been executed
        in the current QA session and returned a successful, non-empty result.

        Returns:
            Tuple[bool, Optional[str]]:
              - bool indicating if this call is an unnecessary duplicate.
              - reason/feedback string for the model if it is a duplicate.
        """
        sig = self.get_tool_signature(tool_name, arguments)
        record = self.executed_tools.get(sig)
        if not record:
            return False, None

        # Do not block if the previous call failed or had an execution error
        if not record.get("success", False):
            return False, None

        # Do not block if previous result was unavailable or empty/not found
        data = record.get("data")
        if data is None:
            return False, None
        if isinstance(data, (list, dict, str)) and len(data) == 0:
            return False, None

        first_turn = record.get("turn_index", "earlier")
        feedback = (
            f"[DUPLICATE TOOL CALL] You already called '{tool_name}' with these exact arguments in Turn {first_turn}, "
            f"and the result is already available in your conversation history. "
            f"Do not repeat identical calls. Please use the existing findings above, investigate a different path, "
            f"or synthesize your final answer."
        )
        return True, feedback

    def record_tool_result(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        success: bool,
        data: Any = None,
        error: Any = None,
        turn_index: Optional[int] = None,
    ) -> None:
        """
        Records the outcome of a tool execution for session-wide duplicate detection.
        """
        sig = self.get_tool_signature(tool_name, arguments)
        self.executed_tools[sig] = {
            "tool_name": tool_name,
            "arguments": arguments,
            "success": success,
            "data": data,
            "error": error,
            "turn_index": turn_index if turn_index is not None else self.turn_count,
            "call_count": self.executed_tools.get(sig, {}).get("call_count", 0) + 1,
        }

    def record_turn(self) -> None:
        """Records the progression of an agent turn."""
        self.turn_count += 1

    def check_pre_turn_limits(self) -> Optional[StopReason]:
        """Checks turn and execution time limits before starting an agent turn."""
        elapsed = time.perf_counter() - self.start_time
        if elapsed >= self.config.max_execution_seconds:
            logger.warning(f"LoopGuardrails: Task timeout exceeded ({elapsed:.1f}s >= {self.config.max_execution_seconds}s)")
            return StopReason.EXECUTION_TIMEOUT

        if self.turn_count >= self.config.max_agent_turns:
            logger.warning(f"LoopGuardrails: Max turns exceeded ({self.turn_count} >= {self.config.max_agent_turns})")
            return StopReason.MAX_TURNS_EXCEEDED

        return None

    def record_tool_call(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Tuple[Optional[StopReason], bool]:
        """
        Records a tool invocation, validates execution caps, and inspects for repetition loops.

        Returns:
            Tuple[Optional[StopReason], bool]:
              - StopReason if a hard cap or repetition limit was violated (or None)
              - bool indicating if a repetition warning should be emitted to the model
        """
        self.tool_call_count += 1

        if self.tool_call_count > self.config.max_tool_calls:
            logger.warning(f"LoopGuardrails: Max tool calls exceeded ({self.tool_call_count} > {self.config.max_tool_calls})")
            return StopReason.MAX_TOOL_CALLS_EXCEEDED, False

        # Command-specific rate limiting
        if tool_name in COMMAND_TOOL_NAMES:
            self.command_count += 1
            if self.command_count > self.config.max_command_executions:
                logger.warning(f"LoopGuardrails: Max command executions exceeded ({self.command_count} > {self.config.max_command_executions})")
                return StopReason.MAX_COMMANDS_EXCEEDED, False

        # Normalized signature hashing
        sig = self.get_tool_signature(tool_name, arguments)
        self.recent_signatures.append(sig)

        logger.debug(f"LoopGuardrails: Tool call #{self.tool_call_count}: {tool_name} (recent signatures: {len(self.recent_signatures)})")

        # Check consecutive identical calls at the tail
        consecutive_count = 0
        for prior_sig in reversed(self.recent_signatures):
            if prior_sig == sig:
                consecutive_count += 1
            else:
                break

        if consecutive_count >= self.config.max_repeated_tool_calls:
            logger.warning(f"LoopGuardrails: Repeated tool call loop detected ({consecutive_count} consecutive identical calls for '{tool_name}'). Last 5 signatures: {self.recent_signatures[-5:]}")
            return StopReason.REPEATED_TOOL_CALL_LIMIT, False

        should_warn = (consecutive_count == self.config.max_repeated_tool_calls - 1)
        if should_warn:
            logger.warning(f"LoopGuardrails: Warning - approaching repeated call limit ({consecutive_count} consecutive for '{tool_name}')")
        return None, should_warn

    def sanitize_observation(self, data: Any) -> Any:
        """
        Truncates observation payloads exceeding max_observation_bytes to prevent token context blowup.
        """
        if data is None:
            return None

        max_bytes = self.config.max_observation_bytes

        if isinstance(data, str):
            if len(data.encode("utf-8", errors="ignore")) > max_bytes:
                truncated_text = data[: max_bytes // 2]
                return (
                    f"{truncated_text}\n\n"
                    f"... [OBSERVATION TRUNCATED: Original size exceeded {max_bytes} bytes limit. "
                    f"Please refine query or read specific ranges.]"
                )
            return data

        try:
            serialized = json.dumps(data, default=str)
            if len(serialized.encode("utf-8", errors="ignore")) > max_bytes:
                return {
                    "_truncated": True,
                    "preview": serialized[: max_bytes // 2],
                    "warning": f"Observation exceeded max byte size ({max_bytes} bytes).",
                }
        except Exception:
            pass

        return data
