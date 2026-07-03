// VEGAH Compliance Intelligence — TypeScript Types
// Mirrors the backend Pydantic schemas exactly

export type AgentStatus = "pending" | "active" | "complete" | "error" | "skipped";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type GapType =
  | "missing_capability"
  | "partial_match"
  | "compliance_risk"
  | "timeline_conflict"
  | "certification_required";

export type ModelProvider = "claude" | "openai";

// ── Agent Event (SSE payload) ─────────────────────────────────────────────────

export interface AgentEvent {
  event_type: "agent_start" | "agent_complete" | "agent_error" | "pipeline_complete";
  agent_name: string;
  status: AgentStatus;
  message: string;
  data?: Record<string, unknown>;
  timestamp: string;
}

// ── Agent State (UI tracking) ─────────────────────────────────────────────────

export interface AgentState {
  name: string;
  displayName: string;
  status: AgentStatus;
  message: string;
  startTime?: number;
  endTime?: number;
  data?: Record<string, unknown>;
}

// ── Capability Match ──────────────────────────────────────────────────────────

export interface CapabilityChunk {
  chunk_id: string;
  capability_id: string;
  capability_name: string;
  text: string;
  match_score: number;
  source: string;
}

export interface CapabilityMatch {
  requirement_id: string;
  matched_chunks: CapabilityChunk[];
  best_score: number;
  has_strong_match: boolean;
}

// ── Compliance Gap ────────────────────────────────────────────────────────────

export interface ComplianceGap {
  requirement_id: string;
  requirement_text: string;
  gap_type: GapType;
  risk_level: RiskLevel;
  description: string;
  recommendation: string;
  matched_capability?: string;
  match_score?: number;
}

// ── Validation ────────────────────────────────────────────────────────────────

export interface ValidationFlag {
  flag_id: string;
  requirement_id?: string;
  issue: string;
  flag_type: string;
  severity: RiskLevel;
  suggested_fix: string;
}

export interface ValidationResult {
  passed: boolean;
  confidence_score: number;
  flags: ValidationFlag[];
  hallucinations_detected: number;
  unsupported_claims: string[];
  needs_reasoning_retry: boolean;
  validation_notes: string;
}

// ── Reasoning ─────────────────────────────────────────────────────────────────

export interface ReasoningResult {
  overall_compliance_score: number;
  gaps: ComplianceGap[];
  strong_alignments: string[];
  critical_risks: string[];
  executive_summary_points: string[];
  recommended_sections_to_address: string[];
  reasoning_model_used: string;
}

// ── Proposal ──────────────────────────────────────────────────────────────────

export interface ProposalSection {
  title: string;
  content: string;
  order: number;
}

export interface ProposalResult {
  proposal_title: string;
  company_name: string;
  rfp_reference: string;
  generated_at: string;
  model_used: string;
  overall_score: number;
  markdown_content: string;
  sections: ProposalSection[];
  word_count: number;
}

// ── Pipeline Result ───────────────────────────────────────────────────────────

export interface PipelineResult {
  session_id: string;
  proposal: ProposalResult;
  validation?: ValidationResult;
  reasoning?: ReasoningResult;
}

// ── Upload State ──────────────────────────────────────────────────────────────

export interface UploadedFiles {
  rfpFile: File | null;
  capabilityFile: File | null;
}
