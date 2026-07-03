"""
VEGAH Compliance Intelligence — Central Configuration
Loads all environment variables and exposes typed settings to the application.
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = Field(default="VEGAH Compliance Intelligence", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    # In local development we enable debug by default to simplify CORS and testing.
    debug: bool = Field(default=True, alias="DEBUG")

    # ── LLM Keys ─────────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    groq_api_key: str = Field(alias="GROQ_API_KEY")

    # ── Qdrant ────────────────────────────────────────────────────────────────
    qdrant_url: str = Field(alias="QDRANT_URL")
    qdrant_api_key: str = Field(alias="QDRANT_API_KEY")

    # ── Collection Names ──────────────────────────────────────────────────────
    capabilities_collection: str = Field(
        default="vegah_capabilities", alias="CAPABILITIES_COLLECTION"
    )
    proposals_collection: str = Field(
        default="vegah_proposals", alias="PROPOSALS_COLLECTION"
    )

    # ── Model Names ───────────────────────────────────────────────────────────
    default_reasoning_model: str = Field(default="claude", alias="DEFAULT_REASONING_MODEL")
    groq_model: str = Field(default="llama-3.1-8b-instant", alias="GROQ_MODEL")
    claude_model: str = Field(default="claude-3-5-sonnet-20241022", alias="CLAUDE_MODEL")
    openai_model: str = Field(default="gpt-4o", alias="OPENAI_MODEL")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")

    # ── RAG ───────────────────────────────────────────────────────────────────
    embedding_dimensions: int = Field(default=1536, alias="EMBEDDING_DIMENSIONS")
    top_k_results: int = Field(default=5, alias="TOP_K_RESULTS")
    chunk_size: int = Field(default=512, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=64, alias="CHUNK_OVERLAP")

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="ALLOWED_ORIGINS",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        # In debug/dev mode: allow all origins so Next.js works on any port (3000, 3001, etc.)
        if self.debug:
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton — call this everywhere instead of os.environ."""
    return Settings()
