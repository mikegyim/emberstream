"""FastAPI application factory and lifespan."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI

from .db import init_db
from .routers import health, query, telemetry, ws
from .services.ingest import start_consumers
from .services.stream import EventBus
from .utils.logging import configure_logging
from .utils.metrics import setup_metrics

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and tear down shared resources."""
    configure_logging()
    logger.info("startup_begin")

    bus = EventBus()
    await bus.connect()
    await init_db()
    await bus.ensure_group("broadcaster")
    await bus.ensure_group("embedder")

    app.state.bus = bus
    app.state.consumers = start_consumers(bus)
    logger.info("startup_complete")

    try:
        yield
    finally:
        logger.info("shutdown_begin")
        for task in app.state.consumers:
            task.cancel()
        await bus.close()
        logger.info("shutdown_complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="EmberStream",
        description="Real-time telemetry platform with a RAG query layer.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(telemetry.router)
    app.include_router(query.router)
    app.include_router(ws.router)

    setup_metrics(app)
    return app


app = create_app()
