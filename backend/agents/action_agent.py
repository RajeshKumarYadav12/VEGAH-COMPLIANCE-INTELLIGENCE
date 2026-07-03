"""
VEGAH Compliance Intelligence — Action Agent
Generates the final executive markdown proposal summary.
Uses Claude 3.5 Sonnet or GPT-4o.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import anthropic
from openai import AsyncOpenAI
from groq import AsyncGroq

from config import get_settings
from models.schemas import AgentStatus, ProposalResult, ProposalSection
from models.state import RFPState

logger = logging.getLogger(__name__)
settings = get_settings()

anthropic_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
groq_client = AsyncGroq(api_key=settings.groq_api_key)


ACTION_SYSTEM_PROMPT = """You are a senior technical proposal writer at VEGAH, drafting an executive-level response to a corporate RFP.

Your proposal must be:
- Professional, precise, and compelling
- Grounded exclusively in the verified capability data provided
- Structured in clear markdown sections
- Free of marketing fluff — every claim must be backed by evidence from the context
- Tailored specifically to the client's requirements and concerns

The proposal must include these sections in order:
1. Executive Summary (2-3 paragraphs)
2. Understanding of Requirements (brief restatement showing comprehension)
3. VEGAH Capability Alignment (table format: Requirement | VEGAH Capability | Match Confidence | Status)
4. Compliance & Risk Analysis (structured list of risks and mitigations)
5. Identified Gaps & Mitigation Plan (honest gap disclosure with action plan)
6. Implementation Roadmap (timeline with milestones)
7. Why VEGAH (differentiation based on capability evidence)
8. Next Steps & Call to Action

IMPORTANT: 
- Use proper markdown: headers (##), tables (|--|--|), bullet lists, bold, italic
- For the capability alignment table, only list capabilities that appear in the context
- Be honest about gaps — propose realistic mitigation plans
- Sign off as: "VEGAH Compliance Intelligence Team"

Return the complete proposal as a single raw markdown string — no JSON wrapping needed."""


def _build_action_context(state: RFPState) -> str:
    """Builds the comprehensive context for proposal generation."""
    extraction = state["extraction_result"]
    rag = state["rag_result"]
    reasoning = state["reasoning_result"]
    validation = state["validation_result"]

    lines = [
        f"# RFP: {extraction.rfp_title}",
        f"**Issuer:** {extraction.rfp_issuer}",
        f"**Deadline:** {extraction.rfp_deadline or 'TBD'}",
        f"**Overview:** {extraction.project_overview}",
        "",
        "## Key Deliverables",
        *[f"- {d}" for d in extraction.key_deliverables],
        "",
        "## Evaluation Criteria",
        *[f"- {c}" for c in extraction.evaluation_criteria],
        "",
        f"## Gap Analysis Results",
        f"- Overall Compliance Score: {reasoning.overall_compliance_score:.1f}%",
        f"- Strong Alignments: {', '.join(reasoning.strong_alignments) or 'None'}",
        f"- Critical Risks: {', '.join(reasoning.critical_risks) or 'None'}",
        "",
        "## Executive Summary Points from Analysis",
        *[f"- {p}" for p in reasoning.executive_summary_points],
        "",
        "## Compliance Gaps (Verified)",
    ]

    # Filter to only non-flagged gaps for the proposal
    flagged_req_ids = {f.requirement_id for f in (validation.flags if validation else []) if f.severity.value in ("critical", "high")}

    for gap in reasoning.gaps:
        confidence_note = "(deterministically verified)" if gap.requirement_id not in flagged_req_ids else "(needs clarification)"
        lines.append(
            f"- [{gap.risk_level.upper()}] {gap.requirement_id}: {gap.gap_type} — {gap.description} | "
            f"Recommendation: {gap.recommendation} {confidence_note}"
        )

    lines.extend([
        "",
        "## Capability Context (Retrieved from Knowledge Base)",
    ])

    if rag and rag.matches:
        for match in rag.matches:
            if match.has_strong_match and match.matched_chunks:
                best = match.matched_chunks[0]
                lines.append(f"- **{match.requirement_id}** → {best.capability_name} ({best.match_score:.0%} match)")

    lines.extend([
        "",
        "## Requirements to Address",
        *[f"- {s}" for s in reasoning.recommended_sections_to_address],
    ])

    return "\n".join(lines)


async def action_agent(state: RFPState) -> RFPState:
    """
    Node 6: Action Agent
    - Builds comprehensive context from all prior agent outputs
    - Calls Claude or GPT-4o to generate executive markdown proposal
    - Stores proposal result with metadata
    """
    logger.info(f"[Action Agent] Starting — session: {state['session_id']}")

    if not state.get("reasoning_result"):
        return {
            **state,
            "action_status": AgentStatus.ERROR,
            "pipeline_error": "Action Agent: Missing reasoning result.",
        }

    context = _build_action_context(state)
    reasoning_model_key = state.get("reasoning_model", settings.default_reasoning_model)
    model_name = settings.claude_model if reasoning_model_key == "claude" else settings.openai_model

    try:
        # Force fallback to Groq due to Anthropic/OpenAI billing errors
        response = await groq_client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": ACTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Draft the executive proposal for this RFP using the context below.\n\n"
                        f"{context}\n\n"
                        f"Generate the complete, polished markdown proposal now."
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        markdown_content = response.choices[0].message.content

        extraction = state["extraction_result"]
        reasoning = state["reasoning_result"]

        # Build sections from markdown
        sections = _parse_markdown_sections(markdown_content)

        proposal = ProposalResult(
            proposal_title=f"VEGAH Response to: {extraction.rfp_title}",
            company_name="VEGAH",
            rfp_reference=extraction.rfp_title,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model_used=model_name,
            overall_score=reasoning.overall_compliance_score,
            markdown_content=markdown_content,
            sections=sections,
            word_count=len(markdown_content.split()),
        )

        logger.info(
            f"[Action Agent] Complete — {proposal.word_count} words, "
            f"{len(sections)} sections"
        )

        return {
            **state,
            "action_status": AgentStatus.COMPLETE,
            "proposal_result": proposal,
            "pipeline_complete": True,
        }

    except Exception as e:
        logger.exception(f"[Action Agent] Error: {e}")
        return {
            **state,
            "action_status": AgentStatus.ERROR,
            "pipeline_error": f"Action Agent failed: {str(e)}",
        }


def _parse_markdown_sections(markdown: str) -> list[ProposalSection]:
    """Parses top-level ## headings into ProposalSection objects."""
    sections: list[ProposalSection] = []
    current_title = ""
    current_lines: list[str] = []
    order = 0

    for line in markdown.split("\n"):
        if line.startswith("## "):
            if current_title:
                sections.append(
                    ProposalSection(
                        title=current_title,
                        content="\n".join(current_lines).strip(),
                        order=order,
                    )
                )
                order += 1
                current_lines = []
            current_title = line[3:].strip()
        elif line.startswith("# "):
            current_title = line[2:].strip()
        else:
            if current_title:
                current_lines.append(line)

    if current_title and current_lines:
        sections.append(
            ProposalSection(
                title=current_title,
                content="\n".join(current_lines).strip(),
                order=order,
            )
        )

    return sections
