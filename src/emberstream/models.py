"""Pydantic models and SQLAlchemy ORM definitions."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import get_settings

EMBEDDING_DIM = get_settings().embedding_dim


# --- SQLAlchemy ORM ---------------------------------------------------------


class Base(DeclarativeBase):
    pass


class Telemetry(Base):
    """Telemetry record + its vector embedding, co-located for cheap RAG."""

    __tablename__ = "telemetry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sensor_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    value: Mapped[float] = mapped_column(Float)
    location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


# --- API schemas ------------------------------------------------------------


class TelemetryIn(BaseModel):
    """Inbound telemetry event."""

    sensor_id: str = Field(..., min_length=1, max_length=64, examples=["sensor-01"])
    kind: str = Field(..., min_length=1, max_length=32, examples=["temperature"])
    value: float = Field(..., examples=[42.7])
    location: str | None = Field(default=None, max_length=128, examples=["grid-A-7"])
    notes: str | None = Field(default=None, max_length=2048)


class TelemetryOut(BaseModel):
    """Telemetry event as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ts: datetime
    sensor_id: str
    kind: str
    value: float
    location: str | None = None
    notes: str | None = None


class QueryIn(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    top_k: int | None = Field(default=None, ge=1, le=50)


class QueryHit(BaseModel):
    telemetry: TelemetryOut
    similarity: float


class QueryOut(BaseModel):
    question: str
    answer: str | None
    context: list[QueryHit]


def now_utc() -> datetime:
    return datetime.now(UTC)
