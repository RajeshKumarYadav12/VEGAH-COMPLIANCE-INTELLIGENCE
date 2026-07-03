"""
VEGAH Compliance Intelligence — Validator Agent
Dual-mode validation:
  1. DETERMINISTIC: String-match capability claims against retrieved Qdrant chunks
  2. LLM: Claude/GPT-4o cross-checks reasoning quality for hallucinations
"""

from __future__ import annotations

import json
import logging
import re
from pydantic import ValidationError

import anthropic
from openai import AsyncOpenAI

from config import get_settings
from models.schemas import (
    AgentStatus,
    RiskLevel,
    ValidationFlag,
    ValidationResult,
)
from models.state import RFPState

logger = logging.getLogger(__name__)
settings = get_settings()

anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

HALLUCINATION_CONFIDENCE_THRESHOLD = 75.0  # Below this, flag as needing retry


VALIDATOR_SYSTEM_PROMPT = """You are a strict compliance auditor validating an AI-generated gap analysis for accuracy.

Your role is to:
1. Check if every capability claim in the gap analysis is actually supported by the retrieved capability context
2. Flag any "hallucinated" capabilities that appear in the analysis but NOT in the context
3. Check for logical contradictions (e.g., marking something as "strong alignment" when the match score is < 0.4)
4. Verify that compliance risk levels are proportional to the actual gaps found
5. Assign a confidence score (0-100) reflecting the overall quality and accuracy of the analysis

Return ONLY valid JSON matching this schema:
{
  "passed": boolean,
  "confidence_score": number (0-100),
  "flags": [
    {
      "flag_id": "FLAG-001",
      "requirement_id": "REQ-001 or null",
      "issue": "string — precise description of the problem",
      "flag_type": "hallucination|unsupported_claim|missing_evidence|contradiction",
      "severity": "critical|high|medium|low",
      "suggested_fix": "string"
    }
  ],
  "hallucinations_detected": number,
  "unsupported_claims": ["string"],
  "needs_reasoning_retry": boolean,
  "validation_notes": "string"
}"""


def _deterministic_check(state: RFPState) -> list[ValidationFlag]:
    """
    DETERMINISTIC VALIDATION PASS:
    Verifies that each capability name referenced in the reasoning gaps
    actually appears in the RAG-retrieved chunks for that requirement.
    """
    flags: list[ValidationFlag] = []
    reasoning = state.get("reasoning_result")
    rag_result = state.get("rag_result")

    if not reasoning or not rag_result:
        return flags

    # Build lookup: requirement_id → set of retrieved capability names (lowercased)
    capability_name_lookup: dict[str, set[str]] = {}
    for match in rag_result.matches:
        names = {chunk.capability_name.lower() for chunk in match.matched_chunks}
        capability_name_lookup[match.requirement_id] = names

    flag_counter = 1
    for gap in reasoning.gaps:
        if not gap.matched_capability:
            continue

        # Check if the matched capability is in the retrieved chunks for this requirement
        retrieved_names = capability_name_lookup.get(gap.requirement_id, set())
        if not retrieved_names:
            continue  # No RAG data for this requirement — skip deterministic check

        claimed_name = gap.matched_capability.lower()

        # Fuzzy check: is the claimed name a substring of any retrieved name or vice versa?
        name_supported = any(
            claimed_name in retrieved_name or retrieved_name in claimed_name
            for retrieved_name in retrieved_names
        )

        if not name_supported and gap.match_score and gap.match_score > 0.5:
            flags.append(
                ValidationFlag(
                    flag_id=f"FLAG-{flag_counter:03d}",
                    requirement_id=gap.requirement_id,
                    issue=(
                        f"Capability '{gap.matched_capability}' claimed as matched for {gap.requirement_id} "
                        f"but not found in retrieved chunks: {list(retrieved_names)[:3]}"
                    ),
                    flag_type="unsupported_claim",
                    severity=RiskLevel.HIGH,
                    suggested_fix=(
                        f"Verify capability name matches exactly one of: {list(retrieved_names)[:5]}"
                    ),
                )
            )
            flag_counter += 1

    # Check strong_alignments claims — score should be >= threshold
    match_score_lookup: dict[str, float] = {
        m.requirement_id: m.best_score for m in rag_result.matches
    }

    for req_id in reasoning.strong_alignments:
        score = match_score_lookup.get(req_id, 0.0)
        if score < 0.5:
            flags.append(
                ValidationFlag(
                    flag_id=f"FLAG-{flag_counter:03d}",
                    requirement_id=req_id,
                    issue=(
                        f"{req_id} listed as 'strong alignment' but RAG match score is only {score:.2%}"
                    ),
                    flag_type="contradiction",
                    severity=RiskLevel.HIGH,
                    suggested_fix=(
                        f"Remove {req_id} from strong_alignments or lower its classification."
                    ),
                )
            )
            flag_counter += 1

    return flags


def _build_validation_context(state: RFPState, deterministic_flags: list[ValidationFlag]) -> str:
    """Builds context for the LLM validation pass."""
    reasoning = state["reasoning_result"]
    rag_result = state["rag_result"]

    lines = [
        "# Gap Analysis to Validate",
        f"Overall Score: {reasoning.overall_compliance_score}%",
        f"Gaps: {len(reasoning.gaps)}",
        f"Critical Risks: {reasoning.critical_risks}",
        f"Strong Alignments: {reasoning.strong_alignments}",
        "",
        "## Deterministic Flags Already Found:",
    ]

    if deterministic_flags:
        for f in deterministic_flags:
            lines.append(f"- [{f.severity}] {f.issue}")
    else:
        lines.append("- None found")

    lines.append("\n## Retrieved Capability Context (Source of Truth):")
    if rag_result and rag_result.matches:
        for match in rag_result.matches[:5]:  # Show top 5 for context
            lines.append(f"\n### {match.requirement_id} (best score: {match.best_score:.2%})")
            for chunk in match.matched_chunks[:2]:
                lines.append(f"  - {chunk.capability_name}: {chunk.text[:200]}...")

    lines.append("\n## Gap Analysis Claims:")
    for gap in reasoning.gaps:
        lines.append(
            f"- {gap.requirement_id}: {gap.gap_type} | {gap.risk_level} | "
            f"matched: {gap.matched_capability or 'none'} ({gap.match_score or 0:.2%})"
        )

    return "\n".join(lines)


async def validator_agent(state: RFPState) -> RFPState:
    """
    Node 5: Validator Agent
    1. Runs deterministic string-match validation
    2. Runs LLM cross-check for hallucinations and logical errors
    3. Sets needs_reasoning_retry = True if critical issues are found
    """
    logger.info(f"[Validator Agent] Starting — session: {state['session_id']}")

    if not state.get("reasoning_result"):
        return {
            **state,
            "validator_status": AgentStatus.ERROR,
            "pipeline_error": "Validator Agent: No reasoning result to validate.",
        }

    # Pass 1: Deterministic
    deterministic_flags = _deterministic_check(state)
    logger.info(f"[Validator Agent] Deterministic pass: {len(deterministic_flags)} flags found")

    # Pass 2: LLM validation
    reasoning_model_key = state.get("reasoning_model", settings.default_reasoning_model)
    validation_context = _build_validation_context(state, deterministic_flags)

    try:
        if reasoning_model_key == "claude":
            response = await anthropic_client.messages.create(
                model=settings.claude_model,
                max_tokens=4096,
                system=VALIDATOR_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"Validate this gap analysis:\n\n{validation_context}\n\nReturn ONLY the JSON object.",
                    }
                ],
                temperature=0.0,
            )
            raw = response.content[0].text
        else:
            response = await openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": VALIDATOR_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Validate this gap analysis:\n\n{validation_context}\n\nReturn ONLY the JSON object.",
                    },
                ],
                temperature=0.0,
                max_tokens=4096,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content

        # Clean markdown fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        validation_result = ValidationResult(**parsed)

        # Merge deterministic flags into LLM result
        all_flags = deterministic_flags + validation_result.flags
        validation_result.flags = all_flags
        validation_result.hallucinations_detected += len(
            [f for f in deterministic_flags if f.flag_type == "hallucination"]
        )

        # Decide retry: critical deterministic flags or LLM says retry
        needs_retry = (
            validation_result.needs_reasoning_retry
            or any(f.severity in (RiskLevel.CRITICAL, RiskLevel.HIGH) for f in deterministic_flags)
        ) and state.get("retry_count", 0) < 2

        validation_result.needs_reasoning_retry = needs_retry

        logger.info(
            f"[Validator Agent] Complete — passed: {validation_result.passed}, "
            f"confidence: {validation_result.confidence_score:.1f}%, "
            f"flags: {len(all_flags)}, retry: {needs_retry}"
        )

        return {
            **state,
            "validator_status": AgentStatus.COMPLETE,
            "validation_result": validation_result,
        }

    except Exception as e:
        logger.exception(f"[Validator Agent] Error: {e}")
        # Non-fatal — return a permissive result and continue
        fallback_result = ValidationResult(
            passed=True,
            confidence_score=60.0,
            flags=deterministic_flags,
            hallucinations_detected=0,
            unsupported_claims=[],
            needs_reasoning_retry=False,
            validation_notes=f"LLM validation failed ({e}). Deterministic checks only applied.",
        )
        return {
            **state,
            "validator_status": AgentStatus.COMPLETE,
            "validation_result": fallback_result,
        }
