"""WebSocket endpoint that streams every ingested event to subscribers."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.broadcast import broadcaster

router = APIRouter()


@router.websocket("/ws/telemetry")
async def telemetry_socket(websocket: WebSocket) -> None:
    await broadcaster.connect(websocket)
    try:
        while True:
            # We don't expect inbound messages, but we read to keep the
            # connection alive and detect disconnects promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
    except Exception:
        await broadcaster.disconnect(websocket)
        raise
