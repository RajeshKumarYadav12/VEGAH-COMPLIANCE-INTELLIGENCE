"""
VEGAH Compliance Intelligence — Embeddings Service
Wraps OpenAI text-embedding-3-small with:
  - Semantic chunking (sentence-aware, token-limited chunks)
  - Batch embedding with retry + exponential backoff
  - Rate limit handling
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Optional

import tiktoken
from openai import AsyncOpenAI, RateLimitError, APIError

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    """
    Generates OpenAI embeddings for text chunks.
    Uses text-embedding-3-small (1536 dimensions, cost-effective).
    """

    MODEL = settings.embedding_model
    DIMENSIONS = settings.embedding_dimensions
    BATCH_SIZE = 10           # Reduced to avoid rate limits
    MAX_RETRIES = 2
    RETRY_DELAY = 1.0         # Base delay in seconds (doubles each retry, max ~60s)
    INTER_BATCH_DELAY = 0.5   # Delay between batches to stay under RPM limit

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text))

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text string."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Embeds a list of texts in batches with retry logic.
        Returns list of embedding vectors in the same order as input texts.
        """
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.BATCH_SIZE):
            batch = texts[i: i + self.BATCH_SIZE]
            try:
                embeddings = await self._embed_with_retry(batch)
            except Exception as e:
                # In development mode, allow a deterministic fallback so uploads/tests can proceed
                if settings.debug:
                    logger.warning(f"Embedding failed in dev mode, using feature hashing fallback: {e}")
                    import re, hashlib
                    embeddings = []
                    for text in batch:
                        vec = [0.1] * self.DIMENSIONS
                        for w in re.findall(r'\w+', text.lower()):
                            vec[int(hashlib.md5(w.encode()).hexdigest(), 16) % self.DIMENSIONS] += 2.0
                        norm = sum(x**2 for x in vec) ** 0.5
                        embeddings.append([x/norm for x in vec] if norm else vec)
                else:
                    raise
            all_embeddings.extend(embeddings)
            # Small delay between batches to stay under OpenAI RPM limits
            if i + self.BATCH_SIZE < len(texts):
                await asyncio.sleep(self.INTER_BATCH_DELAY)

        return all_embeddings

    async def _embed_with_retry(
        self, texts: list[str], attempt: int = 0
    ) -> list[list[float]]:
        try:
            response = await self.client.embeddings.create(
                input=texts,
                model=self.MODEL,
                dimensions=self.DIMENSIONS,
            )
            # Sort by index to maintain order (OpenAI doesn't guarantee order)
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]

        except RateLimitError as e:
            if attempt >= self.MAX_RETRIES:
                logger.error(f"Rate limit exceeded after {self.MAX_RETRIES} retries. Giving up.")
                raise
            # Check if it's a hard quota error
            error_msg = str(e).lower()
            if "quota" in error_msg or "insufficient" in error_msg:
                logger.error("OpenAI API out of quota. Failing fast.")
                raise
                
            delay = min(self.RETRY_DELAY * (2 ** attempt), 10.0)
            logger.warning(f"Rate limited (429). Retrying in {delay:.1f}s (attempt {attempt + 1}/{self.MAX_RETRIES})")
            await asyncio.sleep(delay)
            return await self._embed_with_retry(texts, attempt + 1)

        except APIError as e:
            if attempt >= self.MAX_RETRIES:
                raise
            delay = min(self.RETRY_DELAY * (2 ** attempt), 30.0)
            logger.warning(f"API error: {e}. Retrying in {delay:.1f}s (attempt {attempt + 1})")
            await asyncio.sleep(delay)
            return await self._embed_with_retry(texts, attempt + 1)


class SemanticChunker:
    """
    Splits long text into semantically meaningful chunks.
    Strategy:
      1. Split into sentences
      2. Group sentences into chunks of ~CHUNK_SIZE tokens
      3. Apply CHUNK_OVERLAP token overlap between adjacent chunks
    """

    CHUNK_SIZE = settings.chunk_size
    CHUNK_OVERLAP = settings.chunk_overlap

    def __init__(self):
        self._tokenizer = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text))

    def split_into_sentences(self, text: str) -> list[str]:
        """Splits text into sentences using regex."""
        # Handle common abbreviations that shouldn't split sentences
        text = re.sub(r'\b(Mr|Mrs|Dr|Prof|Sr|Jr|vs|etc|i\.e|e\.g)\.\s', r'\1<DOT> ', text)
        sentences = re.split(r'(?<=[.!?])\s+', text)
        # Restore abbreviation dots
        return [s.replace('<DOT>', '.').strip() for s in sentences if s.strip()]

    def chunk_text(self, text: str, source_id: str = "") -> list[dict]:
        """
        Returns a list of chunk dicts with text, token_count, and chunk_index.
        """
        sentences = self.split_into_sentences(text)
        chunks: list[dict] = []
        current_sentences: list[str] = []
        current_tokens = 0
        chunk_index = 0

        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)

            # If a single sentence exceeds chunk size, split it by words
            if sentence_tokens > self.CHUNK_SIZE:
                if current_sentences:
                    chunks.append(self._build_chunk(current_sentences, chunk_index, source_id))
                    chunk_index += 1
                    current_sentences = []
                    current_tokens = 0
                # Force-split long sentence
                word_chunks = self._split_by_words(sentence, self.CHUNK_SIZE)
                for wc in word_chunks:
                    chunks.append({
                        "text": wc,
                        "token_count": self.count_tokens(wc),
                        "chunk_index": chunk_index,
                        "source_id": source_id,
                    })
                    chunk_index += 1
                continue

            if current_tokens + sentence_tokens > self.CHUNK_SIZE:
                # Save current chunk
                chunks.append(self._build_chunk(current_sentences, chunk_index, source_id))
                chunk_index += 1

                # Apply overlap: keep the last N tokens worth of sentences
                overlap_sentences, overlap_tokens = self._get_overlap_sentences(current_sentences)
                current_sentences = overlap_sentences + [sentence]
                current_tokens = overlap_tokens + sentence_tokens
            else:
                current_sentences.append(sentence)
                current_tokens += sentence_tokens

        # Flush remaining sentences
        if current_sentences:
            chunks.append(self._build_chunk(current_sentences, chunk_index, source_id))

        return chunks

    def _build_chunk(self, sentences: list[str], index: int, source_id: str) -> dict:
        text = " ".join(sentences)
        return {
            "text": text,
            "token_count": self.count_tokens(text),
            "chunk_index": index,
            "source_id": source_id,
        }

    def _get_overlap_sentences(self, sentences: list[str]) -> tuple[list[str], int]:
        """Returns the last N sentences that fit within CHUNK_OVERLAP tokens."""
        overlap: list[str] = []
        total_tokens = 0
        for sentence in reversed(sentences):
            t = self.count_tokens(sentence)
            if total_tokens + t > self.CHUNK_OVERLAP:
                break
            overlap.insert(0, sentence)
            total_tokens += t
        return overlap, total_tokens

    def _split_by_words(self, text: str, max_tokens: int) -> list[str]:
        """Splits a long string into word-level chunks of max_tokens each."""
        words = text.split()
        chunks: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for word in words:
            wt = self.count_tokens(word)
            if current_tokens + wt > max_tokens and current:
                chunks.append(" ".join(current))
                current = [word]
                current_tokens = wt
            else:
                current.append(word)
                current_tokens += wt

        if current:
            chunks.append(" ".join(current))

        return chunks
