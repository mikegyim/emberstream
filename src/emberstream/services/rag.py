"""Retrieval-Augmented Generation: embed question, retrieve, synthesize."""
from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import Settings, get_settings
from ..models import QueryHit, QueryOut, Telemetry, TelemetryOut
from .embeddings import EmbeddingProvider, get_embeddings

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = (
    "You are a telemetry analyst. Answer the user's question using ONLY the "
    "telemetry events provided as context. Be concise. If the context does not "
    "contain enough information to answer, say so explicitly."
)


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system: str, user: str) -> str:
        ...


class BedrockLLM(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        import boto3

        self._client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
        self._model = settings.completion_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
    async def complete(self, system: str, user: str) -> str:
        def call() -> str:
            body = json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 512,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                }
            )
            resp = self._client.invoke_model(modelId=self._model, body=body)
            payload = json.loads(resp["body"].read())
            return payload["content"][0]["text"]

        return await asyncio.to_thread(call)


class OpenAILLM(LLMProvider):
    def __init__(self, settings: Settings) -> None:
        from openai import AsyncOpenAI

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI provider")
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_completion_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=0.5, max=4))
    async def complete(self, system: str, user: str) -> str:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=512,
        )
        return resp.choices[0].message.content or ""


def get_llm() -> LLMProvider | None:
    settings = get_settings()
    if settings.llm_provider == "bedrock":
        return BedrockLLM(settings)
    if settings.llm_provider == "openai":
        return OpenAILLM(settings)
    return None


class RAGService:
    """Combines an embedder, a vector store, and an LLM into a query pipeline."""

    def __init__(
        self,
        embedder: EmbeddingProvider | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        self._embedder = embedder or get_embeddings()
        self._llm = llm if llm is not None else get_llm()

    async def query(
        self,
        session: AsyncSession,
        question: str,
        top_k: int | None = None,
    ) -> QueryOut:
        settings = get_settings()
        k = top_k or settings.retrieval_top_k

        # 1. Embed the question.
        q_emb = await self._embedder.embed(question)

        # 2. Retrieve top-k by cosine distance.
        stmt = (
            select(
                Telemetry,
                Telemetry.embedding.cosine_distance(q_emb).label("distance"),
            )
            .order_by("distance")
            .limit(k)
        )
        result = await session.execute(stmt)
        rows = result.all()

        hits = [
            QueryHit(
                telemetry=TelemetryOut.model_validate(row.Telemetry),
                similarity=float(1 - row.distance),
            )
            for row in rows
        ]

        # 3. Synthesize an answer if an LLM is configured.
        answer: str | None = None
        if self._llm is not None and hits:
            context = "\n".join(
                f"- ts={h.telemetry.ts.isoformat()} sensor={h.telemetry.sensor_id} "
                f"kind={h.telemetry.kind} value={h.telemetry.value} "
                f"location={h.telemetry.location or 'n/a'} notes={h.telemetry.notes or 'n/a'}"
                for h in hits
            )
            user_msg = f"Question: {question}\n\nTelemetry context:\n{context}"
            answer = await self._llm.complete(SYSTEM_PROMPT, user_msg)

        return QueryOut(question=question, answer=answer, context=hits)
