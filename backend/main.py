"""
VEGAH Compliance Intelligence — FastAPI Application
Main entry point with SSE streaming endpoint and capability upload.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import uuid

# Monkeypatch for LangGraph/langchain-core backwards compatibility bug
import langchain
langchain.debug = False
from itertools import islice
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from config import get_settings
from models.schemas import AgentStatus, AgentEvent
from models.state import RFPState
from agents.graph import rfp_graph
from services.csv_parser import CapabilityParser
from services.embeddings import EmbeddingService
from services.qdrant_service import QdrantService

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Multi-agent AI system for RFP intake, compliance analysis, and proposal generation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Service singletons ────────────────────────────────────────────────────────
qdrant_service = QdrantService()
embedding_service = EmbeddingService()
csv_parser = CapabilityParser()


# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Ensure Qdrant collections exist on startup."""
    try:
        await qdrant_service.ensure_collections_exist()
        cap_count = await qdrant_service.count_capabilities()
        logger.info(
            f"VEGAH RFP Intelligence started. "
            f"Qdrant capabilities: {cap_count} vectors."
        )
    except Exception as e:
        logger.error(f"Startup warning — Qdrant connection issue: {e}")


# ── Root endpoint ─────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    """Root endpoint — API documentation available at /docs"""
    return {
        "message": "VEGAH Compliance Intelligence API",
        "version": settings.app_version,
        "docs": "http://localhost:8000/docs",
        "health": "http://localhost:8000/health",
        "endpoints": {
            "POST /upload-capabilities": "Upload capability matrix (CSV/JSON)",
            "POST /process-rfp": "Process RFP with streaming response",
            "GET /health": "Health check"
        }
    }


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    cap_count = 0
    qdrant_ok = False
    try:
        cap_count = await qdrant_service.count_capabilities()
        qdrant_ok = True
    except Exception as e:
        logger.warning(f"Health check — Qdrant unavailable: {e}")

    return {
        "status": "healthy" if qdrant_ok else "degraded",
        "app": settings.app_name,
        "version": settings.app_version,
        "qdrant_connected": qdrant_ok,
        "capabilities_stored": cap_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Upload capabilities endpoint ─────────────────────────────────────────────
@app.post("/upload-capabilities")
async def upload_capabilities(
    file: UploadFile = File(..., description="CSV or JSON capability matrix"),
):
    """
    Parses, embeds, and upserts a company capability matrix into Qdrant.
    Idempotent — re-uploading the same file will overwrite existing vectors.
    """
    suffix = os.path.splitext(file.filename or "capabilities.csv")[1].lower()
    if suffix not in (".csv", ".json"):
        raise HTTPException(
            status_code=400,
            detail="Only .csv and .json files are supported for capability matrices.",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        capabilities = csv_parser.parse(tmp_path)
        if not capabilities:
            # Provide a short preview of the uploaded file to help debug parsing issues
            try:
                with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
                    preview_lines = [line.rstrip() for line in islice(f, 10)]
                    preview = "\\n".join(preview_lines) if preview_lines else "(empty file)"
            except Exception:
                preview = "(unable to read file preview)"

            raise HTTPException(
                status_code=400,
                detail=(
                    "No valid capabilities found in file. "
                    "File preview (first 10 lines): " + preview
                ),
            )

        chunks = csv_parser.capabilities_to_text_chunks(capabilities)
        texts = [c["text"] for c in chunks]

        logger.info(f"Embedding {len(chunks)} capability chunks...")
        try:
            embeddings = await embedding_service.embed_batch(texts)
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Embedding service error: {str(e)}. Please check your OpenAI API key.",
            )

        await qdrant_service.ensure_collections_exist()
        upserted = await qdrant_service.upsert_capability_chunks(chunks, embeddings)

        return {
            "success": True,
            "capabilities_parsed": len(capabilities),
            "chunks_embedded": upserted,
            "message": f"Successfully ingested {len(capabilities)} capabilities into knowledge base.",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload capabilities error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process capabilities: {str(e)}",
        )
    finally:
        os.unlink(tmp_path)


# ── RFP processing endpoint (SSE streaming) ───────────────────────────────────
@app.post("/process-rfp")
async def process_rfp(
    rfp_file: UploadFile = File(..., description="RFP PDF document"),
    capability_file: UploadFile = File(None, description="Optional: Updated capability CSV/JSON"),
    reasoning_model: str = Form(default="claude", description="'claude' or 'openai'"),
):
    """
    Processes an uploaded RFP PDF through the 6-agent pipeline.
    Returns a Server-Sent Events stream with real-time agent status updates.
    """
    try:
        if not rfp_file.filename or not rfp_file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="RFP file must be a PDF.")

        if reasoning_model not in ("claude", "openai"):
            raise HTTPException(status_code=400, detail="reasoning_model must be 'claude' or 'openai'.")

        logger.info(f"Processing RFP: {rfp_file.filename}, Model: {reasoning_model}")

        # Save uploaded files to temp
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            shutil.copyfileobj(rfp_file.file, tmp_pdf)
            pdf_path = tmp_pdf.name

        csv_path = None
        if capability_file and capability_file.filename:
            suffix = os.path.splitext(capability_file.filename)[1].lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_csv:
                shutil.copyfileobj(capability_file.file, tmp_csv)
                csv_path = tmp_csv.name

        session_id = str(uuid.uuid4())
        logger.info(f"Starting RFP pipeline — session: {session_id}, model: {reasoning_model}")

        return StreamingResponse(
            _stream_pipeline(session_id, pdf_path, csv_path, reasoning_model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Process RFP error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process RFP: {str(e)}",
        )


async def _stream_pipeline(
    session_id: str,
    pdf_path: str,
    csv_path: str | None,
    reasoning_model: str,
) -> AsyncGenerator[str, None]:
    """
    Runs the LangGraph pipeline and yields SSE events for each agent state change.
    """

    async def astream_with_pings(agen, ping_interval=5.0):
        iterator = agen.__aiter__()
        while True:
            task = asyncio.create_task(iterator.__anext__())
            while True:
                done, pending = await asyncio.wait([task], timeout=ping_interval)
                if done:
                    try:
                        yield task.result()
                    except StopAsyncIteration:
                        return
                    break
                else:
                    yield "ping"

    def sse(event: AgentEvent) -> str:
        return f"data: {event.model_dump_json()}\n\n"

    def make_event(
        agent_name: str,
        status: AgentStatus,
        event_type: str,
        message: str = "",
        data: dict = None,
    ) -> AgentEvent:
        return AgentEvent(
            event_type=event_type,
            agent_name=agent_name,
            status=status,
            message=message,
            data=data,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Initial state
    initial_state: RFPState = {
        "pdf_path": pdf_path,
        "csv_path": csv_path,
        "session_id": session_id,
        "reasoning_model": reasoning_model,
        "intake_status": AgentStatus.PENDING,
        "extraction_status": AgentStatus.PENDING,
        "rag_status": AgentStatus.PENDING,
        "reasoning_status": AgentStatus.PENDING,
        "validator_status": AgentStatus.PENDING,
        "action_status": AgentStatus.PENDING,
        "file_health": None,
        "extraction_result": None,
        "rag_result": None,
        "reasoning_result": None,
        "validation_result": None,
        "proposal_result": None,
        "retry_count": 0,
        "pipeline_error": None,
        "pipeline_complete": False,
        "raw_pdf_text": None,
    }

    agent_order = [
        ("intake", "Intake Agent"),
        ("extraction", "Extraction Agent"),
        ("rag", "RAG/Knowledge Agent"),
        ("reasoning", "Reasoning Agent"),
        ("validator", "Validator Agent"),
        ("action", "Action Agent"),
    ]

    # Emit pending for all agents
    for _, display_name in agent_order:
        yield sse(make_event(display_name, AgentStatus.PENDING, "agent_start", "Waiting..."))

    try:
        previous_statuses = {}
        current_state = initial_state

        async for state_chunk in astream_with_pings(rfp_graph.astream(initial_state), 5.0):
            if state_chunk == "ping":
                yield ": keepalive\n\n"
                continue

            # LangGraph returns {node_name: state} for each step
            for node_name, new_state in state_chunk.items():
                current_state = new_state

                # Map node to display name
                display_map = {
                    "intake": "Intake Agent",
                    "extraction": "Extraction Agent",
                    "rag": "RAG/Knowledge Agent",
                    "reasoning": "Reasoning Agent",
                    "reasoning_retry": "Reasoning Agent",
                    "validator": "Validator Agent",
                    "action": "Action Agent",
                }
                display_name = display_map.get(node_name, node_name)

                # Emit active event
                yield sse(make_event(display_name, AgentStatus.ACTIVE, "agent_start", f"{display_name} processing..."))

                # Small delay to allow frontend to update
                await asyncio.sleep(0.1)

                # Determine completion status
                status_field = f"{node_name.replace('_retry', '')}_status"
                agent_status = new_state.get(status_field, AgentStatus.COMPLETE)

                # Build data payload for the event
                event_data = _extract_event_data(node_name, new_state)

                if agent_status == AgentStatus.ERROR:
                    yield sse(make_event(
                        display_name,
                        AgentStatus.ERROR,
                        "agent_error",
                        new_state.get("pipeline_error", "Unknown error"),
                        event_data,
                    ))
                else:
                    yield sse(make_event(
                        display_name,
                        AgentStatus.COMPLETE,
                        "agent_complete",
                        f"{display_name} completed successfully.",
                        event_data,
                    ))

        # Final event
        if current_state.get("pipeline_complete") and current_state.get("proposal_result"):
            proposal = current_state["proposal_result"]
            yield sse(make_event(
                "Pipeline",
                AgentStatus.COMPLETE,
                "pipeline_complete",
                "RFP processing complete. Proposal ready.",
                {
                    "session_id": session_id,
                    "proposal": proposal.model_dump(),
                    "validation": current_state["validation_result"].model_dump() if current_state.get("validation_result") else None,
                    "reasoning": current_state["reasoning_result"].model_dump() if current_state.get("reasoning_result") else None
                },
            ))
        elif current_state.get("pipeline_error"):
            yield sse(make_event(
                "Pipeline",
                AgentStatus.ERROR,
                "pipeline_complete",
                f"Pipeline failed: {current_state['pipeline_error']}",
            ))

    except Exception as e:
        logger.exception(f"Pipeline streaming error: {e}")
        yield sse(make_event(
            "Pipeline",
            AgentStatus.ERROR,
            "pipeline_complete",
            f"Internal error: {str(e)}",
        ))
    finally:
        # Cleanup temp files
        try:
            os.unlink(pdf_path)
            if csv_path:
                os.unlink(csv_path)
        except Exception:
            pass


def _extract_event_data(node_name: str, state: RFPState) -> dict:
    """Extracts relevant summary data for each agent's SSE event."""
    data = {}

    if node_name == "intake" and state.get("file_health"):
        health = state["file_health"]
        data = {
            "pdf_pages": health.pdf_page_count,
            "pdf_valid": health.pdf_valid,
            "csv_valid": health.csv_valid,
            "warnings": health.warnings[:3],
        }
    elif node_name == "extraction" and state.get("extraction_result"):
        er = state["extraction_result"]
        data = {
            "rfp_title": er.rfp_title,
            "requirements_count": er.total_requirements,
            "deadline": er.rfp_deadline,
        }
    elif node_name == "rag" and state.get("rag_result"):
        rr = state["rag_result"]
        data = {
            "total_matches": len(rr.matches),
            "strong_matches": sum(1 for m in rr.matches if m.has_strong_match),
            "unmatched_count": len(rr.unmatched_requirement_ids),
            "chunks_retrieved": rr.total_chunks_retrieved,
        }
    elif node_name in ("reasoning", "reasoning_retry") and state.get("reasoning_result"):
        rr = state["reasoning_result"]
        data = {
            "compliance_score": rr.overall_compliance_score,
            "gaps_count": len(rr.gaps),
            "critical_risks": len(rr.critical_risks),
            "model_used": rr.reasoning_model_used,
        }
    elif node_name == "validator" and state.get("validation_result"):
        vr = state["validation_result"]
        data = {
            "passed": vr.passed,
            "confidence_score": vr.confidence_score,
            "flags_count": len(vr.flags),
            "needs_retry": vr.needs_reasoning_retry,
        }
    elif node_name == "action" and state.get("proposal_result"):
        pr = state["proposal_result"]
        data = {
            "word_count": pr.word_count,
            "sections_count": len(pr.sections),
            "overall_score": pr.overall_score,
        }

    return data
