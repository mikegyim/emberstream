"""Redis Streams as the event bus.

The interface is intentionally narrow so a Kafka or Kinesis backend can be
swapped in by implementing the same async functions.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as redis

from ..config import get_settings


class EventBus:
    """Thin wrapper around Redis Streams for at-least-once delivery."""

    def __init__(self, url: str | None = None) -> None:
        settings = get_settings()
        self._url = url or settings.redis_url
        self._stream = settings.stream_name
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        self._client = redis.from_url(self._url, decode_responses=True)
        # Ping to fail fast on bad config.
        await self._client.ping()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            raise RuntimeError("EventBus.connect() not called")
        return self._client

    async def publish(self, payload: dict[str, Any]) -> str:
        """Append an event to the stream. Returns the assigned message ID."""
        return await self.client.xadd(self._stream, {"data": json.dumps(payload, default=str)})

    async def ensure_group(self, group: str) -> None:
        """Create a consumer group if it doesn't already exist."""
        try:
            await self.client.xgroup_create(self._stream, group, id="0", mkstream=True)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def consume(
        self,
        group: str,
        consumer: str,
        *,
        count: int = 16,
        block_ms: int = 5_000,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Yield (message_id, payload) tuples; caller must ack with `ack()`."""
        await self.ensure_group(group)
        while True:
            entries = await self.client.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={self._stream: ">"},
                count=count,
                block=block_ms,
            )
            if not entries:
                continue
            for _, messages in entries:
                for message_id, fields in messages:
                    yield message_id, json.loads(fields["data"])

    async def ack(self, group: str, message_id: str) -> None:
        await self.client.xack(self._stream, group, message_id)
