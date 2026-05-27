"""Background consumers that read from Redis Streams and update Postgres / WS."""
from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select

from ..config import get_settings
from ..db import session_scope
from ..models import Telemetry, TelemetryOut, now_utc
from .broadcast import broadcaster
from .embeddings import EmbeddingProvider, get_embeddings, telemetry_to_text
from .stream import EventBus

logger = structlog.get_logger(__name__)


async def broadcaster_loop(bus: EventBus) -> None:
    """Consumes the event stream and pushes each event to WebSocket clients."""
    settings = get_settings()
    async for msg_id, payload in bus.consume(
        group=settings.broadcaster_group, consumer="broadcaster-1"
    ):
        try:
            await broadcaster.broadcast(payload)
        finally:
            await bus.ack(settings.broadcaster_group, msg_id)


async def embedder_loop(bus: EventBus, embedder: EmbeddingProvider | None = None) -> None:
    """Consumes the event stream, computes embeddings, persists to Postgres."""
    settings = get_settings()
    emb = embedder or get_embeddings()
    async for msg_id, payload in bus.consume(
        group=settings.embedder_group, consumer="embedder-1"
    ):
        try:
            text = telemetry_to_text(
                sensor_id=payload["sensor_id"],
                kind=payload["kind"],
                value=payload["value"],
                location=payload.get("location"),
                notes=payload.get("notes"),
            )
            vector = await emb.embed(text)
            async with session_scope() as session:
                row = Telemetry(
                    id=payload["id"],
                    ts=now_utc(),
                    sensor_id=payload["sensor_id"],
                    kind=payload["kind"],
                    value=payload["value"],
                    location=payload.get("location"),
                    notes=payload.get("notes"),
                    embedding=vector,
                )
                session.add(row)
        except Exception:
            logger.exception("embedder_failed", msg_id=msg_id)
        finally:
            await bus.ack(settings.embedder_group, msg_id)


async def list_recent(limit: int = 50) -> list[TelemetryOut]:
    async with session_scope() as session:
        stmt = select(Telemetry).order_by(Telemetry.ts.desc()).limit(limit)
        rows = (await session.execute(stmt)).scalars().all()
        return [TelemetryOut.model_validate(r) for r in rows]


def start_consumers(bus: EventBus) -> list[asyncio.Task[None]]:
    return [
        asyncio.create_task(broadcaster_loop(bus), name="broadcaster"),
        asyncio.create_task(embedder_loop(bus), name="embedder"),
    ]
