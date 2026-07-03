"""
VEGAH Compliance Intelligence — LangGraph State Machine
Defines the full 6-agent pipeline as a directed graph with conditional routing.

Graph topology:
  intake → extraction → rag → reasoning → validator → (retry or action)
                                              ↑______________|
                                         (if needs_reasoning_retry)
"""

from __future__ import annotations

import logging
from langgraph.graph import StateGraph, END

from models.state import RFPState
from models.schemas import AgentStatus
from agents.intake_agent import intake_agent
from agents.extraction_agent import extraction_agent
from agents.rag_agent import rag_agent
from agents.reasoning_agent import reasoning_agent
from agents.validator_agent import validator_agent
from agents.action_agent import action_agent

logger = logging.getLogger(__name__)

MAX_TOTAL_RETRIES = 2


# ── Conditional routing functions ────────────────────────────────────────────

def route_after_intake(state: RFPState) -> str:
    """Route to extraction or terminate on intake failure."""
    if state.get("intake_status") == AgentStatus.ERROR:
        return "end"
    return "extraction"


def route_after_extraction(state: RFPState) -> str:
    """Route to RAG or terminate on extraction failure."""
    if state.get("extraction_status") == AgentStatus.ERROR:
        return "end"
    return "rag"


def route_after_rag(state: RFPState) -> str:
    """Route to reasoning — RAG failures are non-fatal."""
    if state.get("rag_status") == AgentStatus.ERROR:
        return "end"
    return "reasoning"


def route_after_reasoning(state: RFPState) -> str:
    """Route to validator or terminate on reasoning failure."""
    if state.get("reasoning_status") == AgentStatus.ERROR:
        return "end"
    return "validator"


def route_after_validator(state: RFPState) -> str:
    """
    Core routing logic:
    - If validator says retry AND we haven't exceeded max retries → back to reasoning
    - Otherwise → action (generate proposal)
    """
    validation_result = state.get("validation_result")
    retry_count = state.get("retry_count", 0)

    if (
        validation_result
        and validation_result.needs_reasoning_retry
        and retry_count < MAX_TOTAL_RETRIES
    ):
        logger.info(
            f"[Graph] Routing back to Reasoning (retry {retry_count + 1}/{MAX_TOTAL_RETRIES})"
        )
        return "reasoning_retry"

    if state.get("validator_status") == AgentStatus.ERROR:
        return "action"  # Non-fatal — continue to proposal generation

    return "action"


async def reasoning_with_retry_increment(state: RFPState) -> RFPState:
    """Wrapper that increments retry_count before calling reasoning_agent."""
    new_state = {**state, "retry_count": state.get("retry_count", 0) + 1}
    return await reasoning_agent(new_state)


# ── Build the graph ───────────────────────────────────────────────────────────

def build_rfp_graph() -> StateGraph:
    """Constructs and compiles the full RFP processing LangGraph."""

    graph = StateGraph(RFPState)

    # Add all agent nodes
    graph.add_node("intake", intake_agent)
    graph.add_node("extraction", extraction_agent)
    graph.add_node("rag", rag_agent)
    graph.add_node("reasoning", reasoning_agent)
    graph.add_node("reasoning_retry", reasoning_with_retry_increment)
    graph.add_node("validator", validator_agent)
    graph.add_node("action", action_agent)

    # Set entry point
    graph.set_entry_point("intake")

    # Add conditional edges
    graph.add_conditional_edges(
        "intake",
        route_after_intake,
        {"extraction": "extraction", "end": END},
    )
    graph.add_conditional_edges(
        "extraction",
        route_after_extraction,
        {"rag": "rag", "end": END},
    )
    graph.add_conditional_edges(
        "rag",
        route_after_rag,
        {"reasoning": "reasoning", "end": END},
    )
    graph.add_conditional_edges(
        "reasoning",
        route_after_reasoning,
        {"validator": "validator", "end": END},
    )
    graph.add_conditional_edges(
        "reasoning_retry",
        route_after_reasoning,
        {"validator": "validator", "end": END},
    )
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {"reasoning_retry": "reasoning_retry", "action": "action"},
    )

    # Action always goes to END
    graph.add_edge("action", END)

    return graph.compile()


# Singleton compiled graph — import this in main.py
rfp_graph = build_rfp_graph()
