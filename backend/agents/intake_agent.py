"""
VEGAH Compliance Intelligence — Intake Agent
Validates uploaded file health and prepares the pipeline state.
Uses deterministic logic only (no LLM) — fast, cheap, reliable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from models.schemas import AgentStatus, FileHealthReport
from models.state import RFPState
from services.pdf_parser import PDFParser
from services.csv_parser import CapabilityParser

logger = logging.getLogger(__name__)

pdf_parser = PDFParser()
csv_parser = CapabilityParser()


async def intake_agent(state: RFPState) -> RFPState:
    """
    Node 1: Intake Agent
    - Validates PDF file health (extractable, page count, size)
    - Validates CSV/JSON capability file if present
    - Extracts raw PDF text for downstream agents
    - Routes to error state if critical validation fails
    """
    logger.info(f"[Intake Agent] Starting — session: {state['session_id']}")

    try:
        pdf_path = state["pdf_path"]
        csv_path = state.get("csv_path")

        # ── PDF Validation ────────────────────────────────────────────────────
        pdf_result = pdf_parser.parse(pdf_path)
        meta = pdf_parser.get_metadata_summary(pdf_result)

        warnings: list[str] = list(pdf_result.warnings)
        errors: list[str] = []

        # Check page count
        if pdf_result.page_count == 0:
            errors.append("PDF has zero pages — file may be corrupted.")

        # Check text extractability
        text_extractable = len(pdf_result.full_text.strip()) > 100
        if not text_extractable:
            errors.append(
                "PDF text extraction failed — document may be image-only or password-protected."
            )

        # ── CSV Validation ────────────────────────────────────────────────────
        csv_valid = False
        csv_row_count = 0
        csv_columns: list[str] = []

        if csv_path and Path(csv_path).exists():
            try:
                capabilities = csv_parser.parse(csv_path)
                csv_valid = len(capabilities) > 0
                csv_row_count = len(capabilities)
                if capabilities:
                    # Report the fields present in first capability
                    first = capabilities[0].model_dump()
                    csv_columns = list(first.keys())
                if not csv_valid:
                    warnings.append("Capability file parsed but contains zero valid entries.")
            except Exception as e:
                warnings.append(f"Capability file warning: {str(e)}")
        elif not csv_path:
            warnings.append(
                "No capability CSV provided — RAG will use existing Qdrant knowledge base only."
            )

        # ── Build health report ───────────────────────────────────────────────
        health = FileHealthReport(
            pdf_valid=len(errors) == 0 and text_extractable,
            pdf_page_count=pdf_result.page_count,
            pdf_text_extractable=text_extractable,
            pdf_file_size_kb=pdf_result.file_size_kb,
            csv_valid=csv_valid,
            csv_row_count=csv_row_count,
            csv_columns=csv_columns,
            warnings=warnings,
            errors=errors,
        )

        if errors:
            logger.error(f"[Intake Agent] Fatal errors: {errors}")
            return {
                **state,
                "intake_status": AgentStatus.ERROR,
                "file_health": health,
                "pipeline_error": f"Intake validation failed: {'; '.join(errors)}",
                "raw_pdf_text": None,
            }

        logger.info(
            f"[Intake Agent] Complete — {pdf_result.page_count} pages, "
            f"{len(pdf_result.full_text)} chars, {csv_row_count} capabilities"
        )

        return {
            **state,
            "intake_status": AgentStatus.COMPLETE,
            "file_health": health,
            "raw_pdf_text": pdf_result.full_text,
        }

    except Exception as e:
        logger.exception(f"[Intake Agent] Unexpected error: {e}")
        return {
            **state,
            "intake_status": AgentStatus.ERROR,
            "pipeline_error": f"Intake agent crashed: {str(e)}",
        }
