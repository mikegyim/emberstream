"""Embedding generation, abstracted over Bedrock and OpenAI."""
from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import Settings, get_settings

logger = structlog.get_logger(__name__)


class EmbeddingProvider(ABC):
    """Producer of dense vector embeddings for a text string."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...


class BedrockEmbeddings(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        import boto3  # local import — heavy

        self._client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        self._model = settings.embedding_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
    async def embed(self, text: str) -> list[float]:
        def call() -> list[float]:
            body = json.dumps({"inputText": text})
            resp = self._client.invoke_model(modelId=self._model, body=body)
            payload = json.loads(resp["body"].read())
            return payload["embedding"]

        return await asyncio.to_thread(call)


class OpenAIEmbeddings(EmbeddingProvider):
    def __init__(self, settings: Settings) -> None:
        from openai import AsyncOpenAI

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI provider")
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_embedding_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
    async def embed(self, text: str) -> list[float]:
        resp = await self._client.embeddings.create(model=self._model, input=text)
        return resp.data[0].embedding


class NullEmbeddings(EmbeddingProvider):
    """Returns a zero vector. Used when no LLM provider is configured so the
    rest of the pipeline still runs end-to-end."""

    def __init__(self, settings: Settings) -> None:
        self._dim = settings.embedding_dim

    async def embed(self, text: str) -> list[float]:
        return [0.0] * self._dim


def get_embeddings() -> EmbeddingProvider:
    settings = get_settings()
    if settings.llm_provider == "bedrock":
        return BedrockEmbeddings(settings)
    if settings.llm_provider == "openai":
        return OpenAIEmbeddings(settings)
    logger.warning("embeddings_disabled", reason="llm_provider=none")
    return NullEmbeddings(settings)


def telemetry_to_text(
    sensor_id: str,
    kind: str,
    value: float,
    location: str | None,
    notes: str | None,
) -> str:
    """Stable text representation used for both ingestion and query-time
    embedding. Keep this deterministic — changing it requires a re-embed."""
    parts = [f"sensor={sensor_id}", f"kind={kind}", f"value={value}"]
    if location:
        parts.append(f"location={location}")
    if notes:
        parts.append(f"notes={notes}")
    return " | ".join(parts)