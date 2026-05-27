"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized config. Override via environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "emberstream"
    log_level: str = "INFO"
    environment: Literal["dev", "test", "prod"] = "dev"

    # Storage
    database_url: str = Field(
        default="postgresql+asyncpg://emberstream:emberstream@postgres:5432/emberstream",
        description="Async SQLAlchemy DSN for Postgres+pgvector.",
    )
    redis_url: str = "redis://redis:6379/0"

    # Event bus
    stream_name: str = "telemetry-events"
    broadcaster_group: str = "broadcaster"
    embedder_group: str = "embedder"

    # LLM provider
    llm_provider: Literal["bedrock", "openai", "none"] = "none"
    embedding_model: str = "amazon.titan-embed-text-v2:0"
    completion_model: str = "anthropic.claude-3-haiku-20240307-v1:0"
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_completion_model: str = "gpt-4o-mini"
    aws_region: str = "us-east-1"

    # Vector dimensions — Titan v2 and OpenAI text-embedding-3-small both produce 1536
    embedding_dim: int = 1536

    # Retrieval
    retrieval_top_k: int = 8


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor."""
    return Settings()
