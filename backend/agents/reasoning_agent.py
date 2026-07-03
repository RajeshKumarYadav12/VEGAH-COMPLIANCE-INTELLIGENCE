"""
VEGAH Compliance Intelligence — Reasoning Agent
Performs deep gap analysis and compliance mapping.
Primary: Claude 3.5 Sonnet | Toggle: GPT-4o
"""

from __future__ import annotations

import json
import logging
from pydantic import ValidationError

import anthropic
from openai import AsyncOpenAI
from groq import AsyncGroq

from config import get_settings
from models.schemas import (
    AgentStatus,
    ComplianceGap,
    GapType,
    RiskLevel,
    ReasoningResult,
)
from models.state import RFPState

logger = logging.getLogger(__name__)
settings = get_settings()

anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
groq_client = AsyncGroq(api_key=settings.groq_api_key)

MAX_REASONING_RETRIES = 2

REASONING_SYSTEM_PROMPT = """You are a senior compliance architect and RFP evaluation specialist at VEGAH.

Your task is to perform a comprehensive gap analysis between:
1. The RFP's extracted requirements 
2. The company's matched capabilities from its knowledge base

You must:
- Evaluate each requirement against its top capability matches
- Identify gaps, risks, and strong alignments
- Assign realistic risk levels (critical/high/medium/low) based on evidence
- Calculate an overall compliance score (0-100) reflecting genuine readiness
- Provide actionable recommendations grounded in the provided capability context

CRITICAL RULES:
- Only reference capabilities explicitly mentioned in the provided context — NEVER invent capabilities
- If no capability matches a requirement, flag it as MISSING_CAPABILITY with HIGH or CRITICAL risk
- Be analytically rigorous — this document will be reviewed by legal and executive teams
- Return ONLY valid JSON matching the exact schema provided

Output JSON schema:
{
  "overall_compliance_score": number (0-100),
  "gaps": [
    {
      "requirement_id": "REQ-001",
      "requirement_text": "string",
      "gap_type": "missing_capability|partial_match|compliance_risk|timeline_conflict|certification_required|none|full_match",
      "risk_level": "critical|high|medium|low",
      "description": "string — precise explanation of the gap",
      "recommendation": "string — specific actionable remediation",
      "matched_capability": "string or null — name of best matching capability",
      "match_score": number or null (0.0 to 1.0)
    }
  ],
  "strong_alignments": ["REQ-001", "REQ-003"],
  "critical_risks": ["REQ-007", "REQ-012"],
  "executive_summary_points": ["string"],
  "recommended_sections_to_address": ["string"],
  "reasoning_model_used": "string"
}"""


def _build_reasoning_context(state: RFPState) -> str:
    """Builds the structured context block for the reasoning prompt."""
    extraction = state["extraction_result"]
    rag_result = state["rag_result"]

    lines = [
        f"# RFP: {extraction.rfp_title}",
        f"Issuer: {extraction.rfp_issuer}",
        f"Deadline: {extraction.rfp_deadline or 'Not specified'}",
        f"Overview: {extraction.project_overview}",
        "",
        "## Extracted Requirements with Capability Matches",
        "",
    ]

    # Build a match lookup
    match_lookup = {m.requirement_id: m for m in (rag_result.matches if rag_result else [])}

    for req in extraction.requirements:
        lines.append(f"### {req.requirement_id} [{req.priority.upper()}] — {req.category}")
        lines.append(f"**Requirement:** {req.requirement_text}")

        if req.compliance_rules:
            rules_text = ", ".join(
                f"{r.rule_text} ({'MANDATORY' if r.is_mandatory else 'optional'})"
                for r in req.compliance_rules
            )
            lines.append(f"**Compliance Rules:** {rules_text}")

        if req.timeline_constraint:
            lines.append(f"**Timeline Constraint:** {req.timeline_constraint}")

        match = match_lookup.get(req.requirement_id)
        if match and match.matched_chunks:
            lines.append(f"**Capability Matches (top {len(match.matched_chunks)}):**")
            for chunk in match.matched_chunks[:3]:  # Show top 3 for context
                lines.append(
                    f"  - [{chunk.match_score:.2%} match] {chunk.capability_name}: "
                    f"{chunk.text[:300]}..."
                )
        else:
            lines.append("**Capability Matches:** NONE — No matching company capability found.")

        lines.append("")

    return "\n".join(lines)


async def _call_claude(context: str, model_name: str) -> str:
    # Force fallback to Groq due to Anthropic billing errors
    return await _call_groq(context, settings.groq_model)


async def _call_openai(context: str, model_name: str) -> str:
    # Force fallback to Groq due to OpenAI billing errors
    return await _call_groq(context, settings.groq_model)


async def _call_groq(context: str, model_name: str) -> str:
    response = await groq_client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": REASONING_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Perform the complete gap analysis on this RFP and capabilities context:\n\n{context}\n\nReturn ONLY the JSON object.",
            },
        ],
        temperature=0.1,
        max_tokens=2048,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


async def reasoning_agent(state: RFPState) -> RFPState:
    """
    Node 4: Reasoning Agent
    - Selects model based on state['reasoning_model']
    - Builds rich context from extraction + RAG results
    - Calls Claude 3.5 Sonnet or GPT-4o for deep gap analysis
    - Validates output with Pydantic and retries with corrections
    """
    logger.info(
        f"[Reasoning Agent] Starting — session: {state['session_id']}, "
        f"model: {state.get('reasoning_model', 'claude')}"
    )

    if not state.get("extraction_result") or not state.get("rag_result"):
        return {
            **state,
            "reasoning_status": AgentStatus.ERROR,
            "pipeline_error": "Reasoning Agent: Missing extraction or RAG results.",
        }

    context = _build_reasoning_context(state)
    reasoning_model_key = state.get("reasoning_model", settings.default_reasoning_model)
    model_name = settings.claude_model if reasoning_model_key == "claude" else settings.openai_model

    last_error = ""
    correction_note = ""

    for attempt in range(MAX_REASONING_RETRIES + 1):
        try:
            full_context = context
            if correction_note:
                full_context += f"\n\nCORRECTION REQUIRED: {correction_note}\nFix the issue and return valid JSON."

            if reasoning_model_key == "claude":
                raw = await _call_claude(full_context, model_name)
            elif reasoning_model_key == "groq":
                raw = await _call_groq(full_context, model_name)
            else:
                raw = await _call_openai(full_context, model_name)

            # Strip potential markdown code fences
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            parsed["reasoning_model_used"] = model_name

            result = ReasoningResult(**parsed)

            logger.info(
                f"[Reasoning Agent] Complete — score: {result.overall_compliance_score:.1f}%, "
                f"{len(result.gaps)} gaps, {len(result.critical_risks)} critical"
            )

            return {
                **state,
                "reasoning_status": AgentStatus.COMPLETE,
                "reasoning_result": result,
            }

        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)
            correction_note = f"Validation error: {last_error}"
            logger.warning(f"[Reasoning Agent] Attempt {attempt + 1} failed: {e}")

        except Exception as e:
            error_str = str(e).lower()
            if "insufficient_quota" in error_str or "credit balance" in error_str or "429" in error_str or "400" in error_str:
                logger.warning(f"[Reasoning Agent] Quota/Billing error with {model_name}: {e}. Auto-falling back to Groq.")
                reasoning_model_key = "groq"
                model_name = settings.groq_model
                continue

            logger.exception(f"[Reasoning Agent] Unexpected error: {e}")
            return {
                **state,
                "reasoning_status": AgentStatus.ERROR,
                "pipeline_error": f"Reasoning Agent failed: {str(e)}",
            }

    return {
        **state,
        "reasoning_status": AgentStatus.ERROR,
        "pipeline_error": f"Reasoning Agent failed after {MAX_REASONING_RETRIES + 1} attempts: {last_error}",
    }
