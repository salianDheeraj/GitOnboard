"""
Stage 4 Fact validation, absence claim verification, and evidence sufficiency checking for QALoop.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.services.qa_loop import QALoopResult

logger = logging.getLogger(__name__)

# Expanded dictionary of common architectural entities and their related keywords/aliases
SUSPICIOUS_TERMS = [
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

DIRECT_NEGATION = [
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

SOFT_NEGATION = [
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

ENTITY_CONTEXT = [
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

REPO_CONTEXT = [
    "repository",
    "codebase",
    "project",
    "code",
    "repo",
    "repository",
    "this repo",
    "this project",
]


def is_absence_claim(answer: str) -> bool:
    """
    Improved heuristic: detect if answer claims repository-wide absence.
    Handles direct negation, soft negation, and entity/repo context.
    """
    answer_lower = answer.lower()
    has_direct = any(p in answer_lower for p in DIRECT_NEGATION)
    has_soft = any(p in answer_lower for p in SOFT_NEGATION)
    has_context = (
        any(e in answer_lower for e in ENTITY_CONTEXT) or
        any(r in answer_lower for r in REPO_CONTEXT)
    )
    return has_direct or (has_soft and has_context)


def has_retrieval_been_performed(result: QALoopResult) -> bool:
    """
    Check if any repository retrieval has been performed in this execution.
    Returns True if: search_repository, read_file, or get_symbol was called and succeeded.
    """
    retrieval_tools = ["search_repository", "read_file", "get_symbol", "search_code", "get_code_relationships", "query_rim"]
    for turn in result.turns:
        if turn.tool_call:
            tool_name = turn.tool_call.get("tool_name", "")
            if tool_name in retrieval_tools:
                if turn.tool_observation and turn.tool_observation.get("success", False):
                    return True
    return False


def check_evidence_sufficiency(question: str, result: QALoopResult) -> Tuple[bool, Optional[str]]:
    """
    Evaluate whether the evidence collected so far is sufficient to answer the user's question,
    enabling proactive early stopping and synthesis rather than exhausting execution turns.
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

    # Scenario 1: Relational question where get_code_relationships found relationship
    is_relational_q = any(w in q_lower for w in ["who calls", "what calls", "caller", "callee", "depend", "import", "where is", "inherits", "what does"])
    if is_relational_q and len(successful_graph) >= 1:
        if len(successful_reads) >= 1:
            return True, (
                "[EVIDENCE SUFFICIENT] Structural relationship and relevant code implementation have been inspected. "
                "You have sufficient evidence to provide your final answer now. Do not call additional tools."
            )
        first_graph = successful_graph[0].tool_observation.get("data", {})
        if first_graph.get("resolution") == "STATIC_CONFIRMED" and len(first_graph.get("related", [])) > 0:
            return True, (
                "[EVIDENCE SUFFICIENT] Structural relationships have been confirmed by code graph analysis. "
                "You have sufficient evidence to provide your final answer now. Do not call additional tools."
            )

    # Scenario 2: Functional question where the target function/file has been read
    is_functional_q = any(w in q_lower for w in ["what does", "how does", "explain", "how is", "where is", "definition of"])
    if is_functional_q and len(successful_reads) >= 1:
        return True, (
            "[EVIDENCE SUFFICIENT] The target implementation has been inspected with read_file. "
            "You have sufficient evidence to provide your final answer now. Do not call additional tools."
        )

    return False, None


def retrieval_evidence_supports_absence(result: QALoopResult, answer: str = "") -> Tuple[bool, str]:
    """
    Check if the actual retrieval result data supports an absence claim.
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

        if not turn.tool_observation.get("success", False):
            had_failed_search = True
            continue

        had_successful_retrieval = True
        result_data = turn.tool_observation.get("data", None)

        if tool_name in ("search_repository", "search_code"):
            if isinstance(result_data, list) and len(result_data) > 0:
                for item in result_data:
                    if isinstance(item, dict):
                        sym = item.get("symbol") or ""
                        file_p = item.get("file") or item.get("path") or ""
                        snip = item.get("snippet") or ""
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
                    found_positive_matches.append(f"file content in {file_p}")

    if not had_successful_retrieval:
        if had_failed_search:
            return False, "Failed or errored searches cannot be treated as proof of absence."
        return False, "No retrieval was performed to verify this absence claim."

    # 1. Contradiction Check: If positive evidence was retrieved that contradicts an absence claim
    if found_positive_matches and answer_lower:
        for term, aliases in SUSPICIOUS_TERMS:
            if term in answer_lower and any(neg in answer_lower for neg in ["no ", "not ", "does not", "doesn't", "without"]):
                for turn in result.turns:
                    obs = turn.tool_observation or {}
                    if obs.get("success"):
                        data_str = str(obs.get("data", "")).lower()
                        if any(alias in data_str for alias in aliases):
                            return False, f"Contradicted by evidence: repository search/read observed '{term}' in the codebase."

    # 2. Targeted Query Relevance Check
    if answer_lower:
        claimed_absent = []
        for term, aliases in SUSPICIOUS_TERMS:
            if term in answer_lower and any(neg in answer_lower for neg in ["no ", "not ", "does not", "doesn't", "without"]):
                claimed_absent.append((term, aliases))

        if claimed_absent:
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


def validate_final_answer_against_evidence(
    answer: str,
    result: QALoopResult,
) -> Tuple[bool, Optional[str], str]:
    """
    Stage 4: Validate factual claims in the final answer against tool results
    available in the current QA session.
    """
    if not answer or not answer.strip():
        return False, "Final answer is empty. Please provide your answer based on repository evidence.", answer

    answer_clean = answer.strip()
    contradictions: List[str] = []
    caveats: List[str] = []

    # 1. Check for absence claims
    if is_absence_claim(answer_clean):
        is_supported, reason = retrieval_evidence_supports_absence(result, answer_clean)
        if not is_supported:
            contradictions.append(f"Absence claim unverified: {reason}")

    # 2. Check for contradictions with read_file contents
    inspected_files: Dict[str, Dict[str, Any]] = {}
    for turn in result.turns:
        tc = turn.tool_call or {}
        obs = turn.tool_observation or {}
        if tc.get("tool_name") == "read_file" and obs.get("success") and isinstance(obs.get("data"), dict):
            p = tc.get("arguments", {}).get("path", "")
            if p:
                inspected_files[p] = obs["data"]

    # Check for truncated read caveats
    truncated_files = [p for p, data in inspected_files.items() if data.get("is_truncated") or data.get("_truncated")]
    if truncated_files:
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

        if tname in ("search_repository", "search_code", "get_symbol") and isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    sym_name = item.get("symbol") or item.get("name")
                    file_name = item.get("file") or item.get("path")
                    if sym_name and len(sym_name) > 2:
                        sym_pat = re.compile(rf"\b(no|not|does not contain|does not exist|cannot find|isn't any)\b[^\.\n]*\b{re.escape(sym_name)}\b", re.IGNORECASE)
                        if sym_pat.search(answer_clean):
                            contradictions.append(f"Claim that '{sym_name}' does not exist is contradicted by tool observation in {file_name}.")

        elif tname == "read_file" and isinstance(data, dict):
            file_text = data.get("raw_text") or data.get("content") or ""
            file_name = data.get("path", "")
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
        warning_box = (
            "\n\n> [!WARNING]\n> **Verification Caveat:**\n"
            + "\n".join(f"> - {c}" for c in contradictions)
        )
        caveated_answer = answer_clean + warning_box
        return False, feedback_msg, caveated_answer

    if caveats:
        disclaimer = "\n\n> [!NOTE]\n" + "\n".join(f"> {c}" for c in caveats)
        return True, None, answer_clean + disclaimer

    return True, None, answer_clean
