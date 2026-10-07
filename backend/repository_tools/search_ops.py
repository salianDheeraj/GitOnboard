"""
Search operations for RepositoryToolLayer (search_code, search_repository, fallback).
Extracted from backend.repository_tools.tools to maintain modularity.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.intelligence.notebook import resolve_source_document
from backend.intelligence.retrieval.retriever import HybridRetriever
from backend.models.fact_store import FactFile
from backend.storage import get_storage

logger = logging.getLogger(__name__)


def search_code_ops(
    tool_layer: Any,
    query: str,
    file_pattern: Optional[str] = None,
    max_matches: int = 25,
    max_files_scanned: int = 40,
) -> List[Dict[str, Any]]:
    """
    Performs lexical regex/substring search over source files in Azure Blob Storage.
    Worktrees are temporary and deleted after indexing; all file content is persisted in blobs.
    """
    try:
        max_matches = int(max_matches) if max_matches else 25
        max_files_scanned = int(max_files_scanned) if max_files_scanned else 40
    except (ValueError, TypeError):
        max_matches = 25
        max_files_scanned = 40

    if not query:
        return []

    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    try:
        logger.debug(
            f"[search_code:DIAGNOSTIC] ENTRY query={query!r} repo={tool_layer.repo_name!r} "
            f"db={bool(tool_layer.db)} analysis_id={tool_layer.analysis_id}"
        )
    except Exception:
        pass

    results: List[Dict[str, Any]] = []

    # 1. Local filesystem branch (when repo_root exists)
    if tool_layer.repo_root and tool_layer.repo_root.exists():
        files_scanned = 0
        files_with_matches = 0
        from backend.repository_tools.security import is_binary_file

        for root, dirs, files in os.walk(tool_layer.repo_root):
            dirs[:] = [
                d for d in dirs
                if d not in {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist", "build"}
            ]
            for file in sorted(files):
                if file_pattern:
                    import fnmatch
                    if not fnmatch.fnmatch(file, file_pattern):
                        continue

                files_scanned += 1
                if files_scanned > max_files_scanned:
                    break

                file_path = Path(root) / file
                if is_binary_file(file_path):
                    continue

                try:
                    rel_path = str(file_path.relative_to(tool_layer.repo_root)).replace("\\", "/")
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        raw_content = f.read()

                    if file.endswith(".ipynb"):
                        doc = resolve_source_document(rel_path, raw_content)
                        text = doc.source if not doc.conversion_error else raw_content
                    else:
                        text = raw_content

                    matches_in_file = 0
                    for line_idx, line in enumerate(text.splitlines(), start=1):
                        if pattern.search(line):
                            results.append({
                                "file": rel_path,
                                "path": rel_path,
                                "line": line_idx,
                                "snippet": line.strip()[:200],
                                "match_type": "lexical",
                            })
                            matches_in_file += 1
                            if len(results) >= max_matches:
                                return results
                    if matches_in_file > 0:
                        files_with_matches += 1
                except Exception:
                    continue

            if files_scanned > max_files_scanned:
                break
        return results

    # 2. Azure Blob Storage branch
    if not tool_layer.db or not tool_layer.analysis_id:
        return []

    file_query = (
        tool_layer.db.query(FactFile)
        .filter(FactFile.analysis_id == tool_layer.analysis_id)
        .filter(FactFile.blob_name.isnot(None))
    )

    if file_pattern:
        sql_pattern = file_pattern.replace("*", "%").replace("?", "_")
        file_query = file_query.filter(FactFile.path.ilike(sql_pattern))

    candidate_files = file_query.limit(max_files_scanned).all()
    storage = get_storage()
    files_scanned = 0
    files_with_matches = 0

    for f_rec in candidate_files:
        files_scanned += 1
        if not f_rec.blob_name:
            continue

        try:
            raw_text = storage.get_object_text(f_rec.blob_name)
            if not raw_text:
                continue

            doc = resolve_source_document(f_rec.path, raw_text)
            text = doc.source if not doc.conversion_error else raw_text

            matches_in_file = 0
            for line_idx, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    results.append({
                        "file": f_rec.path,
                        "path": f_rec.path,
                        "line": line_idx,
                        "snippet": line.strip()[:200],
                        "match_type": "lexical",
                    })
                    matches_in_file += 1
                    if len(results) >= max_matches:
                        return results
            if matches_in_file > 0:
                files_with_matches += 1
        except Exception:
            continue

    return results


def search_repository_ops(
    tool_layer: Any,
    query: str,
    limit: int = 10,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Hybrid search using HybridRetriever with comma-separated multi-query batching."""
    try:
        limit = int(limit) if limit else 10
        offset = int(offset) if offset else 0
    except (ValueError, TypeError):
        limit = 10
        offset = 0

    retriever = tool_layer._get_retriever()
    if retriever is None:
        return search_repository_fallback_ops(tool_layer, query, limit, offset)

    sub_queries = [q.strip() for q in query.split(",") if q.strip()]
    if not sub_queries:
        return []

    combined: List[Dict[str, Any]] = []
    seen_keys = set()
    max_total = min(limit * len(sub_queries), 30)

    for sub_query in sub_queries:
        try:
            top_k = max(limit, 10)
            results = retriever.retrieve(sub_query, top_k=top_k)

            for result in results:
                if result.symbol:
                    key = f"sym:{result.file_path}:{result.symbol}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        combined.append({
                            "type": "symbol",
                            "file": result.file_path,
                            "symbol": result.symbol,
                            "lines": f"{result.line_start}-{result.line_end}" if result.line_start else "",
                            "query": sub_query,
                            "match_source": result.score_type or "symbol_index",
                            "score": result.score,
                        })
                else:
                    key = f"code:{result.file_path}:{result.line_number}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        combined.append({
                            "type": "code",
                            "file": result.file_path,
                            "line": result.line_number,
                            "snippet": result.snippet or "",
                            "query": sub_query,
                            "match_source": result.score_type or "hybrid",
                            "score": result.score,
                        })
        except Exception as e:
            logger.debug(f"Error retrieving for query '{sub_query}': {e}")
            continue

    if not combined:
        return search_repository_fallback_ops(tool_layer, query, limit, offset)

    start = offset
    end = offset + max_total
    return combined[start:end]


def search_repository_fallback_ops(
    tool_layer: Any,
    query: str,
    limit: int = 10,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Fallback to original multi-method search when HybridRetriever is unavailable."""
    combined: List[Dict[str, Any]] = []
    seen_keys = set()

    sub_queries = [q.strip() for q in query.split(",") if q.strip()]
    if not sub_queries:
        return []

    max_total = min(limit * len(sub_queries), 30)

    for sub_query in sub_queries:
        # 1. Symbol search
        sym_matches = tool_layer.get_symbol(sub_query)
        for sym in sym_matches[:5]:
            key = f"sym:{sym['file']}:{sym['name']}"
            if key not in seen_keys:
                seen_keys.add(key)
                combined.append({
                    "type": "symbol",
                    "file": sym["file"],
                    "symbol": sym["name"],
                    "symbol_type": sym["symbol_type"],
                    "lines": f"{sym['line_start']}-{sym['line_end']}",
                    "query": sub_query,
                    "match_source": "symbol_index",
                    "score": 0,
                })

        # 2. File path match
        file_matches = tool_layer.find_files(f"*{sub_query}*")
        for f in file_matches[:5]:
            key = f"file:{f['path']}"
            if key not in seen_keys:
                seen_keys.add(key)
                combined.append({
                    "type": "file",
                    "file": f["path"],
                    "size": f.get("size", 0),
                    "query": sub_query,
                    "match_source": "filename_manifest",
                    "score": 0,
                })

        # 3. Lexical search in source files
        lex_matches = tool_layer.search_code(sub_query, max_matches=5)
        for lex in lex_matches:
            key = f"lex:{lex['file']}:{lex['line']}"
            if key not in seen_keys:
                seen_keys.add(key)
                combined.append({
                    "type": "code",
                    "file": lex["file"],
                    "line": lex["line"],
                    "snippet": lex["snippet"],
                    "query": sub_query,
                    "match_source": "lexical",
                    "score": 0,
                })

    start = offset
    end = offset + max_total
    return combined[start:end]
