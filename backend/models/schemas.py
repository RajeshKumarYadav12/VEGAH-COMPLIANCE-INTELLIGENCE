"""
VEGAH Compliance Intelligence — Pydantic v2 Schemas
All agent input/output types are strictly typed here.
Every LLM call is forced to return one of these schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GapType(str, Enum):
    MISSING_CAPABILITY = "missing_capability"
    PARTIAL_MATCH = "partial_match"
    COMPLIANCE_RISK = "compliance_risk"
    TIMELINE_CONFLICT = "timeline_conflict"
    CERTIFICATION_REQUIRED = "certification_required"
    NONE = "none"
    FULL_MATCH = "full_match"


class AgentStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETE = "complete"
    ERROR = "error"
    SKIPPED = "skipped"


class ModelProvider(str, Enum):
    CLAUDE = "claude"
    OPENAI = "openai"


# ─────────────────────────────────────────────────────────────────────────────
# Intake Agent Output
# ─────────────────────────────────────────────────────────────────────────────

class FileHealthReport(BaseModel):
    """Produced by the Intake Agent after validating uploaded files."""
    pdf_valid: bool
    pdf_page_count: int = 0
    pdf_text_extractable: bool = False
    pdf_file_size_kb: float = 0.0
    csv_valid: bool = False
    csv_row_count: int = 0
    csv_columns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Extraction Agent Output
# ─────────────────────────────────────────────────────────────────────────────

class ComplianceRule(BaseModel):
    rule_id: str
    rule_text: str
    standard: Optional[str] = None   # e.g. "ISO 27001", "SOC 2", "GDPR"
    is_mandatory: bool = True


class RFPRequirement(BaseModel):
    requirement_id: str = Field(..., description="Unique ID e.g. REQ-001")
    section: str = Field(..., description="Section of the RFP this came from")
    requirement_text: str
    priority: str = Field(default="medium", description="low | medium | high | critical")
    category: str = Field(default="technical", description="technical | compliance | timeline | financial | functional")
    compliance_rules: list[ComplianceRule] = Field(default_factory=list)
    timeline_constraint: Optional[str] = None
    budget_constraint: Optional[str] = None


class ExtractionResult(BaseModel):
    """Structured output of the Extraction Agent."""
    rfp_title: str
    rfp_issuer: str
    rfp_deadline: Optional[str] = None
    project_overview: str
    total_requirements: int
    requirements: list[RFPRequirement]
    key_deliverables: list[str] = Field(default_factory=list)
    evaluation_criteria: list[str] = Field(default_factory=list)
    raw_compliance_section: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# RAG Agent Output
# ─────────────────────────────────────────────────────────────────────────────

class CapabilityChunk(BaseModel):
    """A single chunk retrieved from the Qdrant capability vector store."""
    chunk_id: str
    capability_id: str
    capability_name: str
    text: str
    match_score: float = Field(..., ge=0.0, le=1.0)
    source: str = "capability_matrix"


class CapabilityMatch(BaseModel):
    """Maps a single RFP requirement to its top-K matching capability chunks."""
    requirement_id: str
    matched_chunks: list[CapabilityChunk]
    best_score: float = 0.0
    has_strong_match: bool = False    # True if best_score >= 0.75


class RAGResult(BaseModel):
    """All capability matches produced by the RAG Agent."""
    matches: list[CapabilityMatch]
    unmatched_requirement_ids: list[str] = Field(default_factory=list)
    total_chunks_retrieved: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Reasoning Agent Output
# ─────────────────────────────────────────────────────────────────────────────

class ComplianceGap(BaseModel):
    requirement_id: str
    requirement_text: str
    gap_type: GapType
    risk_level: RiskLevel
    description: str
    recommendation: str
    matched_capability: Optional[str] = None
    match_score: Optional[float] = None


class ReasoningResult(BaseModel):
    """Deep gap analysis output from the Reasoning Agent."""
    overall_compliance_score: float = Field(..., ge=0.0, le=100.0)
    gaps: list[ComplianceGap]
    strong_alignments: list[str] = Field(default_factory=list, description="Requirement IDs with strong capability match")
    critical_risks: list[str] = Field(default_factory=list, description="Requirement IDs with critical gaps")
    executive_summary_points: list[str] = Field(default_factory=list)
    recommended_sections_to_address: list[str] = Field(default_factory=list)
    reasoning_model_used: str = "claude"


# ─────────────────────────────────────────────────────────────────────────────
# Validator Agent Output
# ─────────────────────────────────────────────────────────────────────────────

class ValidationFlag(BaseModel):
    flag_id: str
    requirement_id: Optional[str] = None
    issue: str
    flag_type: str = Field(..., description="hallucination | unsupported_claim | missing_evidence | contradition")
    severity: RiskLevel
    suggested_fix: str


class ValidationResult(BaseModel):
    """Output of the Validator Agent — deterministic + LLM dual-check."""
    passed: bool
    confidence_score: float = Field(..., ge=0.0, le=100.0)
    flags: list[ValidationFlag] = Field(default_factory=list)
    hallucinations_detected: int = 0
    unsupported_claims: list[str] = Field(default_factory=list)
    needs_reasoning_retry: bool = False
    validation_notes: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Action Agent Output
# ─────────────────────────────────────────────────────────────────────────────

class ProposalSection(BaseModel):
    title: str
    content: str
    order: int


class ProposalResult(BaseModel):
    """Final executive proposal generated by the Action Agent."""
    proposal_title: str
    company_name: str = "VEGAH"
    rfp_reference: str
    generated_at: str
    model_used: str
    overall_score: float
    markdown_content: str
    sections: list[ProposalSection] = Field(default_factory=list)
    word_count: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Capability (for CSV ingestion)
# ─────────────────────────────────────────────────────────────────────────────

class Capability(BaseModel):
    """One row from the company capability matrix CSV."""
    capability_id: str
    name: str
    category: str
    description: str
    certifications: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    maturity_level: str = "production"   # prototype | beta | production | deprecated
    applicable_industries: list[str] = Field(default_factory=list)
    case_studies: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# SSE Event (streaming to frontend)
# ─────────────────────────────────────────────────────────────────────────────

class AgentEvent(BaseModel):
    """Emitted over SSE for each agent state change."""
    event_type: str    # "agent_start" | "agent_complete" | "agent_error" | "pipeline_complete"
    agent_name: str
    status: AgentStatus
    message: str = ""
    data: Optional[dict] = None
    timestamp: str = ""
