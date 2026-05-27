"""REST endpoints for telemetry ingestion and listing."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, status

from ..models import TelemetryIn, TelemetryOut, now_utc
from ..services.ingest import list_recent

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.post(
    "",
    response_model=TelemetryOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a single telemetry event.",
)
async def post_telemetry(event: TelemetryIn, request: Request) -> TelemetryOut:
    bus = request.app.state.bus
    record_id = uuid.uuid4()
    payload = {
        "id": str(record_id),
        **event.model_dump(),
    }
    await bus.publish(payload)
    return TelemetryOut(
        id=record_id,
        ts=now_utc(),
        sensor_id=event.sensor_id,
        kind=event.kind,
        value=event.value,
        location=event.location,
        notes=event.notes,
    )


@router.get(
    "",
    response_model=list[TelemetryOut],
    summary="List recent telemetry events.",
)
async def list_telemetry(limit: int = 50) -> list[TelemetryOut]:
    return await list_recent(limit=min(max(limit, 1), 500))
