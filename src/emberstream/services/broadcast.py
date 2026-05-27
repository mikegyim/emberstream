"""WebSocket connection manager that fans events out to all subscribers."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


class Broadcaster:
    """In-memory connection registry. For multi-replica deploys, swap to
    Redis pub/sub so any pod can publish to clients on any pod."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        logger.info("ws_connected", total=len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        logger.info("ws_disconnected", total=len(self._connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to every connected client. Drops dead conns."""
        body = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        async with self._lock:
            targets = list(self._connections)
        for ws in targets:
            try:
                await ws.send_text(body)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ws_send_failed", error=str(exc))
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.discard(ws)

    @property
    def size(self) -> int:
        return len(self._connections)


# Module-level singleton consumed by the WebSocket router and the stream
# consumer task.
broadcaster = Broadcaster()
