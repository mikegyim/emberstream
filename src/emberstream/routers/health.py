"""Health and readiness probes."""
from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness probe.", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe.", include_in_schema=False)
async def ready(request: Request) -> JSONResponse:
    """Returns 200 only when the event bus is reachable."""
    bus = request.app.state.bus
    try:
        await bus.client.ping()
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "reason": str(exc)},
        )
    return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ready"})
