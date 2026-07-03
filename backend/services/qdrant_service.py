"""
VEGAH Compliance Intelligence — Qdrant Vector DB Service
Real Qdrant Cloud client (no mocks).
Handles:
  - Collection creation with cosine similarity
  - Upsert of company capability chunks with rich metadata
  - Semantic search returning top-K results with scores
  - Past proposal storage for context retrieval
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest,
    ScoredPoint,
    CollectionInfo,
)

from config import get_settings
from models.schemas import CapabilityChunk

logger = logging.getLogger(__name__)
settings = get_settings()


class QdrantService:
    """
    Async Qdrant Cloud client wrapper.
    All methods are async to fit FastAPI's async architecture.
    """

    def __init__(self):
        self.client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
        self.capabilities_collection = settings.capabilities_collection
        self.proposals_collection = settings.proposals_collection
        self.dimensions = settings.embedding_dimensions

    # ── Collection Management ────────────────────────────────────────────────

    async def ensure_collections_exist(self) -> None:
        """Creates required collections if they don't already exist."""
        for collection_name in [self.capabilities_collection, self.proposals_collection]:
            exists = await self._collection_exists(collection_name)
            if not exists:
                await self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=self.dimensions,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection: {collection_name}")
            else:
                logger.info(f"Qdrant collection already exists: {collection_name}")

    async def _collection_exists(self, name: str) -> bool:
        try:
            collections = await self.client.get_collections()
            return any(c.name == name for c in collections.collections)
        except Exception as e:
            logger.warning(f"Could not check collection existence: {e}")
            return False

    async def get_collection_info(self, collection_name: str) -> Optional[CollectionInfo]:
        try:
            return await self.client.get_collection(collection_name)
        except Exception:
            return None

    # ── Upsert Operations ────────────────────────────────────────────────────

    async def upsert_capability_chunks(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> int:
        """
        Upserts capability chunks into the capabilities collection.

        Args:
            chunks: List of dicts from CapabilityParser.capabilities_to_text_chunks()
            embeddings: Parallel list of embedding vectors

        Returns:
            Number of points upserted
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) count mismatch."
            )

        points = []
        for chunk, vector in zip(chunks, embeddings):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["capability_id"] + chunk["text"][:50]))
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "capability_id": chunk["capability_id"],
                        "capability_name": chunk["capability_name"],
                        "text": chunk["text"],
                        "source": "capability_matrix",
                        **chunk.get("metadata", {}),
                    },
                )
            )

        await self.client.upsert(
            collection_name=self.capabilities_collection,
            points=points,
            wait=True,
        )
        logger.info(f"Upserted {len(points)} capability chunks into Qdrant.")
        return len(points)

    async def upsert_proposal_chunk(
        self,
        session_id: str,
        text: str,
        vector: list[float],
        metadata: dict,
    ) -> None:
        """Stores a past proposal chunk for future context retrieval."""
        point_id = str(uuid.uuid4())
        await self.client.upsert(
            collection_name=self.proposals_collection,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "session_id": session_id,
                        "text": text,
                        "source": "past_proposal",
                        **metadata,
                    },
                )
            ],
            wait=True,
        )

    # ── Semantic Search ──────────────────────────────────────────────────────

    async def search_capabilities(
        self,
        query_vector: list[float],
        top_k: int = None,
        filter_category: Optional[str] = None,
    ) -> list[CapabilityChunk]:
        """
        Performs cosine similarity search against the capabilities collection.

        Args:
            query_vector: Embedding vector of the requirement text
            top_k: Number of results to return
            filter_category: Optional Qdrant filter on 'category' payload field

        Returns:
            List of CapabilityChunk sorted by descending match score
        """
        top_k = top_k or settings.top_k_results

        search_filter = None
        if filter_category:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=filter_category),
                    )
                ]
            )

        results: list[ScoredPoint] = await self.client.search(
            collection_name=self.capabilities_collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=search_filter,
            with_payload=True,
        )

        chunks: list[CapabilityChunk] = []
        for point in results:
            payload = point.payload or {}
            chunks.append(
                CapabilityChunk(
                    chunk_id=str(point.id),
                    capability_id=payload.get("capability_id", "unknown"),
                    capability_name=payload.get("capability_name", "Unknown Capability"),
                    text=payload.get("text", ""),
                    match_score=round(point.score, 4),
                    source=payload.get("source", "capability_matrix"),
                )
            )

        return chunks

    async def search_past_proposals(
        self,
        query_vector: list[float],
        top_k: int = 3,
    ) -> list[dict]:
        """Retrieves relevant past proposal chunks for context."""
        results = await self.client.search(
            collection_name=self.proposals_collection,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )
        return [
            {
                "text": (point.payload or {}).get("text", ""),
                "score": round(point.score, 4),
                "session_id": (point.payload or {}).get("session_id", ""),
            }
            for point in results
        ]

    async def delete_all_capabilities(self) -> None:
        """Clears the capabilities collection — use with caution (re-ingestion)."""
        info = await self.get_collection_info(self.capabilities_collection)
        if info:
            await self.client.delete_collection(self.capabilities_collection)
            await self.ensure_collections_exist()
            logger.warning("Capabilities collection cleared and recreated.")

    async def count_capabilities(self) -> int:
        """Returns the number of stored capability vectors."""
        try:
            info = await self.client.get_collection(self.capabilities_collection)
            return info.points_count or 0
        except Exception:
            return 0
