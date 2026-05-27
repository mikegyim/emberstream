"""Unit tests for the WebSocket broadcaster."""
from __future__ import annotations

import pytest

from emberstream.services.broadcast import Broadcaster


class _FakeWS:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.accepted = False
        self.sent: list[str] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, body: str) -> None:
        if self.fail:
            raise RuntimeError("connection broken")
        self.sent.append(body)


@pytest.mark.asyncio
async def test_connect_and_broadcast() -> None:
    b = Broadcaster()
    ws = _FakeWS()
    await b.connect(ws)  # type: ignore[arg-type]
    assert ws.accepted is True
    assert b.size == 1

    await b.broadcast({"hello": "world"})
    assert ws.sent == ['{"hello": "world"}']


@pytest.mark.asyncio
async def test_dead_connections_are_pruned() -> None:
    b = Broadcaster()
    good = _FakeWS()
    bad = _FakeWS(fail=True)
    await b.connect(good)  # type: ignore[arg-type]
    await b.connect(bad)  # type: ignore[arg-type]
    assert b.size == 2

    await b.broadcast({"x": 1})
    # Bad connection should have been removed.
    assert b.size == 1
    assert good.sent == ['{"x": 1}']


@pytest.mark.asyncio
async def test_disconnect_is_idempotent() -> None:
    b = Broadcaster()
    ws = _FakeWS()
    await b.connect(ws)  # type: ignore[arg-type]
    await b.disconnect(ws)  # type: ignore[arg-type]
    await b.disconnect(ws)  # type: ignore[arg-type]
    assert b.size == 0
