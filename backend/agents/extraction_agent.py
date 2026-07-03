"""
VEGAH Compliance Intelligence — Extraction Agent
Extracts structured RFP requirements from raw PDF text.
Uses Groq (llama-3.3-70b-versatile) — ultra-fast, low cost.
Forces strict Pydantic JSON output with auto-retry on validation failure.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from groq import AsyncGroq
from pydantic import ValidationError

from config import get_settings
from models.schemas import (
    AgentStatus,
    ExtractionResult,
    RFPRequirement,
    ComplianceRule,
)
from models.state import RFPState

logger = logging.getLogger(__name__)
settings = get_settings()

groq_client = AsyncGroq(api_key=settings.groq_api_key)

# ── System prompt (cached — static, never changes between runs) ───────────────
EXTRACTION_SYSTEM_PROMPT = """You are an expert RFP (Request for Proposal) analyst with deep knowledge of corporate procurement, compliance frameworks, and technical requirements.

Your task is to extract structured information from a raw RFP document text and return it as a strict JSON object.

Rules:
1. Extract ALL requirements — technical, compliance, timeline, financial, and functional
2. Assign each requirement a unique ID in format REQ-001, REQ-002, etc.
3. Identify compliance rules and standards (ISO, SOC, GDPR, HIPAA, etc.) embedded in requirements
4. Priority levels: "critical" | "high" | "medium" | "low"
5. Categories: "technical" | "compliance" | "timeline" | "financial" | "functional"
6. Return ONLY valid JSON — no markdown, no explanation, no preamble
7. If a field is unknown, use null — never invent information

Output JSON schema:
{
  "rfp_title": "string",
  "rfp_issuer": "string or null",
  "rfp_deadline": "string or null (e.g. '2025-06-30')",
  "project_overview": "string (2-4 sentences)",
  "total_requirements": number,
  "requirements": [
    {
      "requirement_id": "REQ-001",
      "section": "string",
      "requirement_text": "string",
      "priority": "critical|high|medium|low",
      "category": "technical|compliance|timeline|financial|functional",
      "compliance_rules": [
        {
          "rule_id": "CR-001",
          "rule_text": "string",
          "standard": "string or null",
          "is_mandatory": true
        }
      ],
      "timeline_constraint": "string or null",
      "budget_constraint": "string or null"
    }
  ],
  "key_deliverables": ["string"],
  "evaluation_criteria": ["string"],
  "raw_compliance_section": "string or null"
}"""


async def extraction_agent(state: RFPState) -> RFPState:
    """
    Node 2: Extraction Agent
    - Reads raw PDF text from state
    - Calls Groq llama-3.3-70b to extract structured requirements
    - Validates output against ExtractionResult Pydantic schema
    - Auto-retries up to 2 times on validation failure (no blind retry)
    """
    logger.info(f"[Extraction Agent] Starting — session: {state['session_id']}")

    raw_text = state.get("raw_pdf_text", "")
    if not raw_text:
        return {
            **state,
            "extraction_status": AgentStatus.ERROR,
            "pipeline_error": "Extraction Agent: No raw PDF text available.",
        }

    # Truncate to ~12k chars to safely fit within Groq's strict 6000 TPM free tier limit
    if len(raw_text) > 12000:
        raw_text = raw_text[:12000]
        logger.warning("[Extraction Agent] PDF text truncated to 12k chars for TPM limits.")

    user_prompt = f"""Analyze the following RFP document and extract all structured information according to the JSON schema.

RFP Document Text:
---
{raw_text}
---

Return ONLY the JSON object. No additional text."""

    max_retries = 2
    last_error = ""

    for attempt in range(max_retries + 1):
        try:
            response = await groq_client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,   # Low temperature for deterministic structured output
                max_tokens=2048,
                response_format={"type": "json_object"},
            )

            raw_json = response.choices[0].message.content
            parsed = json.loads(raw_json)

            # Validate with Pydantic
            extraction_result = ExtractionResult(**parsed)

            logger.info(
                f"[Extraction Agent] Complete — {extraction_result.total_requirements} requirements "
                f"extracted (attempt {attempt + 1})"
            )

            return {
                **state,
                "extraction_status": AgentStatus.COMPLETE,
                "extraction_result": extraction_result,
            }

        except (json.JSONDecodeError, ValidationError, KeyError) as e:
            last_error = str(e)
            logger.warning(
                f"[Extraction Agent] Validation failed (attempt {attempt + 1}): {e}"
            )
            if attempt < max_retries:
                # Add specific correction guidance to the next prompt
                user_prompt = (
                    f"{user_prompt}\n\n"
                    f"CORRECTION REQUIRED: Your previous response failed validation with this error: {last_error}\n"
                    f"Fix the issue and return valid JSON matching the schema exactly."
                )
                continue

        except Exception as e:
            logger.exception(f"[Extraction Agent] Unexpected error: {e}")
            return {
                **state,
                "extraction_status": AgentStatus.ERROR,
                "pipeline_error": f"Extraction Agent failed: {str(e)}",
            }

    # All retries exhausted
    return {
        **state,
        "extraction_status": AgentStatus.ERROR,
        "pipeline_error": f"Extraction Agent failed after {max_retries + 1} attempts. Last error: {last_error}",
    }
