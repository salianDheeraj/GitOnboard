"""
Tests for Stage 2: Prevent Repetitive Tool Loops.

Validates:
1. Identical tool calls repeated within a session are intercepted.
2. Equivalent arguments with different key ordering or nested structures are detected.
3. Different arguments for the same tool are not blocked.
4. Repeated calls following a failed or empty result are permitted (allows legitimate retries).
5. Duplicate detection across multiple turns (non-consecutive duplicates).
6. Legitimate tool calls still execute normally.
7. Agent receives constructive feedback and can proceed to synthesize a final answer after interception.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent.loop.contracts import AgentLoopConfig, StopReason
from backend.agent.loop.guardrails import LoopGuardrails
from backend.ai.schemas import LLMResponse, TokenUsage
from backend.services.qa_loop import QALoop
from backend.services.qa_protocol import SystemPromptParts


class TestDuplicateCallDetectionGuardrails:
    """Unit tests for LoopGuardrails duplicate detection methods."""

    def test_normalize_arguments_key_order_independence(self):
        """Arguments with different key order must yield the exact same canonical signature."""
        args1 = {"path": "lib/auth.ts", "start_line": 1, "end_line": 100}
        args2 = {"end_line": 100, "path": "lib/auth.ts", "start_line": 1}

        sig1 = LoopGuardrails.normalize_arguments(args1)
        sig2 = LoopGuardrails.normalize_arguments(args2)

        assert sig1 == sig2
        assert sig1 == '{"end_line":100,"path":"lib/auth.ts","start_line":1}'

    def test_normalize_arguments_nested_structures(self):
        """Nested dictionaries and lists are normalized deterministically."""
        args1 = {"filter": {"tags": ["a", "b"], "active": True}, "limit": 10}
        args2 = {"limit": 10, "filter": {"active": True, "tags": ["a", "b"]}}

        sig1 = LoopGuardrails.normalize_arguments(args1)
        sig2 = LoopGuardrails.normalize_arguments(args2)

        assert sig1 == sig2

    def test_duplicate_call_detected_after_successful_execution(self):
        """A call with identical arguments after a successful, non-empty result is flagged as a duplicate."""
        guardrails = LoopGuardrails()
        tool_name = "read_file"
        args = {"path": "lib/auth.ts", "start_line": 1, "end_line": 100}

        # Before execution: not a duplicate
        is_dup, _ = guardrails.is_duplicate_call(tool_name, args)
        assert is_dup is False

        # Record successful result
        guardrails.record_tool_result(
            tool_name=tool_name,
            arguments=args,
            success=True,
            data="export const auth = () => {...}",
            turn_index=1,
        )

        # Subsequent identical call: is a duplicate
        is_dup, feedback = guardrails.is_duplicate_call(tool_name, args)
        assert is_dup is True
        assert "You already called 'read_file' with these exact arguments in Turn 1" in feedback
        assert "Do not repeat identical calls" in feedback

    def test_equivalent_arguments_different_order_detected_as_duplicate(self):
        """Calls with equivalent arguments in different key order are recognized as duplicates."""
        guardrails = LoopGuardrails()
        tool_name = "read_file"
        args_first = {"path": "lib/auth.ts", "start_line": 1, "end_line": 100}
        args_reordered = {"end_line": 100, "path": "lib/auth.ts", "start_line": 1}

        guardrails.record_tool_result(
            tool_name=tool_name,
            arguments=args_first,
            success=True,
            data="export const auth = () => {...}",
            turn_index=2,
        )

        is_dup, feedback = guardrails.is_duplicate_call(tool_name, args_reordered)
        assert is_dup is True
        assert "Turn 2" in feedback

    def test_different_arguments_same_tool_not_blocked(self):
        """Different arguments for the same tool are not blocked."""
        guardrails = LoopGuardrails()
        tool_name = "read_file"

        guardrails.record_tool_result(
            tool_name=tool_name,
            arguments={"path": "lib/auth.ts", "start_line": 1, "end_line": 100},
            success=True,
            data="lines 1-100",
            turn_index=1,
        )

        # Same file, different range -> NOT a duplicate
        is_dup, _ = guardrails.is_duplicate_call(
            tool_name, {"path": "lib/auth.ts", "start_line": 101, "end_line": 200}
        )
        assert is_dup is False

        # Different file -> NOT a duplicate
        is_dup, _ = guardrails.is_duplicate_call(
            tool_name, {"path": "lib/api.ts", "start_line": 1, "end_line": 100}
        )
        assert is_dup is False

    def test_repeated_call_after_failed_result_allowed(self):
        """If previous call failed (e.g. timeout, syntax error, not found), retry is permitted."""
        guardrails = LoopGuardrails()
        tool_name = "read_file"
        args = {"path": "lib/auth.ts", "start_line": 1, "end_line": 100}

        guardrails.record_tool_result(
            tool_name=tool_name,
            arguments=args,
            success=False,
            error={"type": "timeout", "message": "Read timed out"},
            turn_index=1,
        )

        # Should NOT be blocked; retry is permitted
        is_dup, _ = guardrails.is_duplicate_call(tool_name, args)
        assert is_dup is False

    def test_repeated_call_after_empty_result_allowed(self):
        """If previous call returned an empty list/string, retry or re-query is permitted."""
        guardrails = LoopGuardrails()
        tool_name = "search_repository"
        args = {"query": "auth_token"}

        # Search returned no results (empty list)
        guardrails.record_tool_result(
            tool_name=tool_name,
            arguments=args,
            success=True,
            data=[],
            turn_index=1,
        )

        is_dup, _ = guardrails.is_duplicate_call(tool_name, args)
        assert is_dup is False

    def test_duplicate_across_multiple_intervening_turns(self):
        """Duplicates are detected even if several other tool calls occurred in between."""
        guardrails = LoopGuardrails()

        # Turn 1: read_file lib/auth.ts (1-100)
        guardrails.record_tool_result(
            "read_file", {"path": "lib/auth.ts", "start_line": 1, "end_line": 100},
            success=True, data="content", turn_index=1
        )
        # Turn 2: search_repository query="login"
        guardrails.record_tool_result(
            "search_repository", {"query": "login"},
            success=True, data=["match1"], turn_index=2
        )
        # Turn 3: read_file lib/api.ts (1-50)
        guardrails.record_tool_result(
            "read_file", {"path": "lib/api.ts", "start_line": 1, "end_line": 50},
            success=True, data="api content", turn_index=3
        )

        # Turn 4: model attempts to repeat Turn 1!
        is_dup, feedback = guardrails.is_duplicate_call(
            "read_file", {"path": "lib/auth.ts", "start_line": 1, "end_line": 100}
        )
        assert is_dup is True
        assert "Turn 1" in feedback


class TestQALoopDuplicateCallInterception:
    """Integration tests verifying QALoop behavior when a model generates duplicate calls."""

    @pytest.fixture
    def mock_qa_loop(self):
        llm_service = MagicMock()
        tool_dispatch = MagicMock()
        config = AgentLoopConfig(max_turns=10, max_tool_calls=10)
        system_parts = SystemPromptParts(
            grounding_and_protocol_text="Grounding",
            tool_catalog_text="Catalog",
            rim_metadata_text="",
            full_text="System Prompt",
        )
        loop = QALoop(
            llm_service=llm_service,
            tool_dispatch=tool_dispatch,
            config=config,
            system_prompt_parts=system_parts,
            model="qwen3:4b-instruct",
            provider="ollama",
        )
        return loop

    @pytest.mark.asyncio
    async def test_duplicate_call_intercepted_without_tool_dispatch(self, mock_qa_loop):
        """
        When the model issues an exact duplicate of a previous successful tool call:
        - tool_dispatch is NOT invoked a second time.
        - The model receives helpful feedback pointing to existing findings.
        - The model can then synthesize and terminate with a final answer.
        """
        mock_observation = MagicMock(
            success=True,
            error=None,
            data="export function authenticate() { return true; }"
        )
        mock_qa_loop.tool_dispatch.dispatch = MagicMock(return_value=mock_observation)
        mock_qa_loop.tool_dispatch.specs = MagicMock(return_value=[])

        # Sequence of model outputs:
        # Turn 0: read_file(lib/auth.ts, 1, 100) -> executed
        # Turn 1: exact same read_file(lib/auth.ts, 1, 100) -> intercepted by guardrails!
        # Turn 2: final_answer based on findings -> succeeds
        resp0 = LLMResponse(
            content='<tool_call><invoke name="read_file"><parameter name="path">lib/auth.ts</parameter><parameter name="start_line">1</parameter><parameter name="end_line">100</parameter></invoke></tool_call>',
            model="qwen3:4b-instruct",
            provider="ollama",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=30, total_tokens=130),
        )
        resp1_duplicate = LLMResponse(
            content='<tool_call><invoke name="read_file"><parameter name="path">lib/auth.ts</parameter><parameter name="start_line">1</parameter><parameter name="end_line">100</parameter></invoke></tool_call>',
            model="qwen3:4b-instruct",
            provider="ollama",
            usage=TokenUsage(prompt_tokens=150, completion_tokens=30, total_tokens=180),
        )
        resp2_final = LLMResponse(
            content='<tool_call><invoke name="final_answer"><parameter name="answer">The authentication function returns true.</parameter></invoke></tool_call>',
            model="qwen3:4b-instruct",
            provider="ollama",
            usage=TokenUsage(prompt_tokens=200, completion_tokens=40, total_tokens=240),
        )

        mock_qa_loop.llm_service.generate = AsyncMock(side_effect=[resp0, resp1_duplicate, resp2_final])

        result = await mock_qa_loop.run("How does authentication work?")

        # Tool dispatch was called only ONCE (for Turn 0, not Turn 1)
        assert mock_qa_loop.tool_dispatch.dispatch.call_count == 1
        # Final answer was successfully produced
        assert "The authentication function returns true." in result.answer
        assert result.stop_reason == StopReason.COMPLETED_FOR_VERIFICATION
        # Verify that turn 1 recorded the duplicate prevention observation
        dup_turn = result.turns[1]
        assert dup_turn.tool_observation["error"]["type"] == "duplicate_call_prevented"
        assert "[DUPLICATE TOOL CALL]" in dup_turn.tool_observation["formatted_message"]
