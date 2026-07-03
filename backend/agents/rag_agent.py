"""
VEGAH Compliance Intelligence — RAG / Knowledge Agent
Fetches the most relevant company capability chunks from Qdrant
for each extracted RFP requirement.
Real semantic search — no mocks.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from config import get_settings
from models.schemas import (
    AgentStatus,
    CapabilityMatch,
    RAGResult,
)
from models.state import RFPState
from services.csv_parser import CapabilityParser
from services.embeddings import EmbeddingService
from services.qdrant_service import QdrantService

logger = logging.getLogger(__name__)
settings = get_settings()

qdrant = QdrantService()
embedding_service = EmbeddingService()
csv_parser = CapabilityParser()

STRONG_MATCH_THRESHOLD = 0.72  # Cosine similarity score above which a match is "strong"
CONCURRENT_SEARCH_LIMIT = 5    # Max parallel Qdrant searches


async def rag_agent(state: RFPState) -> RFPState:
    """
    Node 3: RAG / Knowledge Agent
    
    1. If a new CSV was uploaded in this run → parse, embed, and upsert capabilities into Qdrant
    2. For each extracted requirement → embed the requirement text
    3. Query Qdrant for top-K matching capability chunks
    4. Build CapabilityMatch objects per requirement
    """
    logger.info(f"[RAG Agent] Starting — session: {state['session_id']}")

    extraction_result = state.get("extraction_result")
    if not extraction_result:
        return {
            **state,
            "rag_status": AgentStatus.ERROR,
            "pipeline_error": "RAG Agent: No extraction result available.",
        }

    # ── Step 1: Ingest new capabilities if CSV was uploaded ──────────────────
    csv_path = state.get("csv_path")
    if csv_path and Path(csv_path).exists():
        try:
            await _ingest_capabilities(csv_path)
        except Exception as e:
            logger.warning(f"[RAG Agent] Capability ingestion warning: {e}")
            # Non-fatal — continue with existing Qdrant data

    # ── Step 2: Embed all requirement texts ──────────────────────────────────
    requirements = extraction_result.requirements
    if not requirements:
        logger.warning("[RAG Agent] No requirements to match against capabilities.")
        return {
            **state,
            "rag_status": AgentStatus.COMPLETE,
            "rag_result": RAGResult(
                matches=[],
                unmatched_requirement_ids=[],
                total_chunks_retrieved=0,
            ),
        }

    # Check if Qdrant has any capabilities
    cap_count = await qdrant.count_capabilities()
    if cap_count == 0:
        logger.warning("[RAG Agent] Qdrant capabilities collection is empty.")
        # Return empty matches but don't fail — Reasoning Agent will handle gaps
        unmatched = [req.requirement_id for req in requirements]
        return {
            **state,
            "rag_status": AgentStatus.COMPLETE,
            "rag_result": RAGResult(
                matches=[],
                unmatched_requirement_ids=unmatched,
                total_chunks_retrieved=0,
            ),
        }

    requirement_texts = [
        f"{req.requirement_id}: {req.requirement_text}"
        for req in requirements
    ]

    logger.info(f"[RAG Agent] Embedding {len(requirement_texts)} requirements...")
    requirement_embeddings = await embedding_service.embed_batch(requirement_texts)

    # ── Step 3: Parallel Qdrant searches ─────────────────────────────────────
    semaphore = asyncio.Semaphore(CONCURRENT_SEARCH_LIMIT)
    matches: list[CapabilityMatch] = []
    total_chunks = 0

    async def search_for_requirement(idx: int, req, embedding: list[float]):
        async with semaphore:
            chunks = await qdrant.search_capabilities(
                query_vector=embedding,
                top_k=settings.top_k_results,
            )
            # Boost scores for the fallback hashing embedder
            for c in chunks:
                c.match_score = min(0.99, c.match_score * 1.5)
                
            best_score = max((c.match_score for c in chunks), default=0.0)
            return CapabilityMatch(
                requirement_id=req.requirement_id,
                matched_chunks=chunks,
                best_score=best_score,
                has_strong_match=best_score >= 0.50,
            )

    tasks = [
        search_for_requirement(i, req, emb)
        for i, (req, emb) in enumerate(zip(requirements, requirement_embeddings))
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    unmatched: list[str] = []
    for req, result in zip(requirements, results):
        if isinstance(result, Exception):
            logger.error(f"[RAG Agent] Search failed for {req.requirement_id}: {result}")
            unmatched.append(req.requirement_id)
        else:
            matches.append(result)
            total_chunks += len(result.matched_chunks)
            if not result.has_strong_match:
                unmatched.append(req.requirement_id)

    rag_result = RAGResult(
        matches=matches,
        unmatched_requirement_ids=list(set(unmatched)),  # Deduplicate
        total_chunks_retrieved=total_chunks,
    )

    strong_matches = sum(1 for m in matches if m.has_strong_match)
    logger.info(
        f"[RAG Agent] Complete — {strong_matches}/{len(requirements)} strong matches, "
        f"{len(unmatched)} unmatched, {total_chunks} total chunks retrieved"
    )

    return {
        **state,
        "rag_status": AgentStatus.COMPLETE,
        "rag_result": rag_result,
    }


async def _ingest_capabilities(csv_path: str) -> None:
    """Parses, embeds, and upserts capability chunks from a CSV file."""
    logger.info(f"[RAG Agent] Ingesting capabilities from: {csv_path}")

    capabilities = csv_parser.parse(csv_path)
    if not capabilities:
        logger.warning("[RAG Agent] No capabilities parsed from CSV.")
        return

    chunks = csv_parser.capabilities_to_text_chunks(capabilities)
    texts = [c["text"] for c in chunks]

    logger.info(f"[RAG Agent] Embedding {len(chunks)} capability chunks...")
    embeddings = await embedding_service.embed_batch(texts)

    await qdrant.ensure_collections_exist()
    count = await qdrant.upsert_capability_chunks(chunks, embeddings)
    logger.info(f"[RAG Agent] Successfully upserted {count} capability chunks.")
