"""
VEGAH Compliance Intelligence — LangGraph State Schema
This TypedDict is the single source of truth passed between all agent nodes.
"""

from __future__ import annotations

from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

from models.schemas import (
    FileHealthReport,
    ExtractionResult,
    RAGResult,
    ReasoningResult,
    ValidationResult,
    ProposalResult,
    AgentStatus,
    ModelProvider,
)


class RFPState(TypedDict):
    """
    Mutable state object threaded through the entire LangGraph pipeline.
    Each agent reads what it needs and writes its output fields.
    """

    # ── Inputs ────────────────────────────────────────────────────────────────
    pdf_path: str                          # Temp path of uploaded PDF
    csv_path: Optional[str]                # Temp path of uploaded capability CSV
    session_id: str                        # Unique run ID (UUID)
    reasoning_model: str                   # "claude" | "openai"

    # ── Agent Statuses ────────────────────────────────────────────────────────
    intake_status: AgentStatus
    extraction_status: AgentStatus
    rag_status: AgentStatus
    reasoning_status: AgentStatus
    validator_status: AgentStatus
    action_status: AgentStatus

    # ── Agent Outputs ─────────────────────────────────────────────────────────
    file_health: Optional[FileHealthReport]
    extraction_result: Optional[ExtractionResult]
    rag_result: Optional[RAGResult]
    reasoning_result: Optional[ReasoningResult]
    validation_result: Optional[ValidationResult]
    proposal_result: Optional[ProposalResult]

    # ── Control Flow ──────────────────────────────────────────────────────────
    retry_count: int                       # Tracks reasoning retries (max 2)
    pipeline_error: Optional[str]          # Captures fatal errors
    pipeline_complete: bool

    # ── Extracted raw text (shared between Extraction and RAG) ────────────────
    raw_pdf_text: Optional[str]
