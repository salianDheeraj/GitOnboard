"""
Summary Pipeline - Orchestrates documentation discovery, classification, budgeting,
optional progressive tool grounding, and summary generation.
"""
from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

import json
import time
import uuid
from backend.ai.service import LLMService, get_llm_service
from backend.repository_tools import RepositoryToolLayer
from .schemas import BudgetedDocContext, SummaryGenerationResult
from .discovery import DocDiscovery
from .classifier import DocClassifier
from .budgeter import DocContextBudgeter
from .generator import SummaryGenerator
from .extractor import EvidenceExtractor
from .hierarchy import RepositoryHierarchyEngine
from .chunker import StructuralMarkdownChunker
from .verifier import ClaimVerifier
from .validator import DeterministicValidator
from .audit import SummaryAuditCollector

logger = logging.getLogger(__name__)


class SummaryPipeline:
    """
    Multi-stage, repository-aware and documentation-aware summary pipeline.
    Degrades gracefully across all edge cases (no docs, huge docs, conflicting docs).
    """

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        discovery: Optional[DocDiscovery] = None,
        classifier: Optional[DocClassifier] = None,
        budgeter: Optional[DocContextBudgeter] = None,
    ):
        self.llm = llm_service or get_llm_service()
        self.classifier = classifier or DocClassifier()
        self.discovery = discovery or DocDiscovery(classifier=self.classifier)
        self.budgeter = budgeter or DocContextBudgeter()
        self.generator = SummaryGenerator(llm_service=self.llm)

    async def run(
        self,
        repo_name: str,
        metadata: Dict[str, Any],
        metrics: Optional[Dict[str, Any]] = None,
        repo_root: Optional[Path | str] = None,
        db: Optional[Session] = None,
        analysis_id: Optional[int] = None,
        user_id: Optional[int] = None,
        enable_progressive_grounding: bool = False,
        verbose_audit: Optional[bool] = None,
    ) -> SummaryGenerationResult:
        metrics = metrics or {}
        discovered_docs = []

        # 1. Discover Documentation
        if repo_root and Path(repo_root).exists():
            discovered_docs = self.discovery.discover_from_directory(repo_root)
        elif db is not None and analysis_id is not None:
            discovered_docs = self.discovery.discover_from_fact_store(db, analysis_id)

        # Extract Evidence and Infer Hierarchy
        extractor = EvidenceExtractor()
        evidence_items = []
        file_paths = []
        if repo_root and Path(repo_root).exists():
            evidence_items = extractor.extract_from_directory(repo_root)
            file_paths = [str(p.relative_to(repo_root)).replace("\\", "/") for p in Path(repo_root).rglob("*") if p.is_file()]

        hierarchy_engine = RepositoryHierarchyEngine()
        deployable_units = hierarchy_engine.infer_hierarchy(file_paths, evidence_items, entrypoints=metadata.get("entrypoints", [])) if file_paths else []

        doc_chunks = []
        for doc in discovered_docs:
            doc_chunks.extend(StructuralMarkdownChunker.chunk_document(doc.content, doc.path))
        verified_claims = ClaimVerifier.verify_technology_claims(evidence_items, doc_chunks)

        # 2. Context Budgeting
        budgeted_context = self.budgeter.budget(discovered_docs)
        logger.info(
            f"SummaryPipeline [{repo_name}]: {len(budgeted_context.primary_docs)} primary docs, "
            f"{len(budgeted_context.supporting_docs)} supporting, {len(budgeted_context.diagram_docs)} diagrams, "
            f"{len(budgeted_context.agent_docs)} agent docs. Total chars: {budgeted_context.total_chars}"
        )

        tool_calls: List[Dict[str, Any]] = []

        # 3. Optional Progressive Grounding (Tool loop if enabled)
        if enable_progressive_grounding and (repo_root or (db and analysis_id)):
            tools = RepositoryToolLayer(
                repo_name=repo_name,
                analysis_id=analysis_id,
                db=db,
                repo_root=repo_root,
                user_id=user_id,
            )
            # If no primary docs exist, inspect entrypoint files directly for grounding
            if not budgeted_context.primary_docs and metadata.get("entrypoints"):
                for ep in metadata.get("entrypoints", [])[:2]:
                    try:
                        read_res = tools.read_file(ep, start_line=1, end_line=100)
                        tool_calls.append({"tool": "read_file", "path": ep, "lines": "1-100"})
                        # Append as primary doc
                        from .schemas import DiscoveredDoc, DocType, DocPriority
                        budgeted_context.primary_docs.append(
                            DiscoveredDoc(
                                path=ep,
                                filename=os.path.basename(ep),
                                doc_type=DocType.PRIMARY_README,
                                priority=DocPriority.HIGH,
                                raw_size=len(read_res.get("raw_text", "")),
                                line_count=read_res.get("total_lines", 0),
                                content=f"// Source entrypoint code sample for grounding:\n{read_res.get('content', '')}",
                            )
                        )
                    except Exception as e:
                        logger.debug(f"Progressive grounding tool read failed: {e}")

        # 4. Generate Grounded Summary
        raw_summary = await self.generator.generate_summary(
            repo_name=repo_name,
            metadata=metadata,
            metrics=metrics,
            doc_context=budgeted_context,
        )

        structured_summary = None
        discrepancies_detected: List[str] = []
        validation_stats: Dict[str, Any] = {}
        summary_md = raw_summary

        # If LLM returned structured JSON, validate and format to markdown
        try:
            raw_data = json.loads(raw_summary)
            if isinstance(raw_data, dict):
                evidence_map = {e.evidence_id: e for e in evidence_items}
                file_paths = [e.file_path for e in evidence_items if e.file_path]
                structured_summary, rejected_claims, validation_stats = DeterministicValidator.validate_and_sanitize(
                    raw_data=raw_data,
                    known_evidence=evidence_map,
                    verified_claims=verified_claims,
                    deployable_units=deployable_units,
                    known_file_paths=file_paths,
                )
                discrepancies_detected = [d.repository_reality for d in structured_summary.discrepancies]

                # Format structured summary to clean Markdown
                md_parts = [
                    f"# {repo_name} — Repository Summary",
                    f"\n## 1. Overview & Purpose\n{structured_summary.overview.text}",
                ]
                if structured_summary.deployable_units:
                    md_parts.append("\n## 2. Deployable Units")
                    for u in structured_summary.deployable_units:
                        md_parts.append(f"- **{u.name}** ({u.unit_type}): {u.summary} (`{u.root_path}`)")
                if structured_summary.technologies:
                    md_parts.append("\n## 3. Tech Stack & Architecture")
                    for t in structured_summary.technologies:
                        md_parts.append(f"- **{t.name}** ({t.category}): {t.status}")
                if structured_summary.discrepancies:
                    md_parts.append("\n## 4. Discrepancies & Notes")
                    for d in structured_summary.discrepancies:
                        md_parts.append(f"- **Claimed**: {d.documented_claim} | **Actual**: {d.repository_reality}")

                summary_md = "\n".join(md_parts)
        except Exception:
            pass

        # 5. Handle Verbose Audit Logging
        is_verbose = verbose_audit
        if is_verbose is None:
            is_verbose = os.getenv("SUMMARY_VERBOSE_AUDIT", "false").lower() in ("true", "1", "yes")

        if is_verbose:
            audit = SummaryAuditCollector()
            audit.metadata = metadata
            audit.evidence_index = [e.model_dump() for e in evidence_items]
            audit.hierarchy = [u.model_dump() for u in deployable_units]
            audit.retrieval_decisions = {
                "selected_evidence_count": len(evidence_items),
                "supplied_units_count": len(deployable_units),
            }
            audit.context_sent_to_llm = str(budgeted_context.model_dump())
            audit.llm_response = {"content": raw_summary}
            audit.validation_results = validation_stats
            audit.final_summary_md = summary_md
            audit.persist_run_artifacts()

        doc_context_stats = {
            "total_chars": budgeted_context.total_chars,
            "primary_count": len(budgeted_context.primary_docs),
            "supporting_count": len(budgeted_context.supporting_docs),
            "diagram_count": len(budgeted_context.diagram_docs),
            "agent_count": len(budgeted_context.agent_docs),
            "omitted_count": len(budgeted_context.omitted_docs),
            "verified_claims_count": len(verified_claims),
        }

        return SummaryGenerationResult(
            summary_markdown=summary_md,
            structured_summary=structured_summary,
            doc_context_stats=doc_context_stats,
            discrepancies_detected=discrepancies_detected,
            tool_calls_made=tool_calls,
        )
