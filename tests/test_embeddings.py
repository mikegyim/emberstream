"""Unit tests for the embedding helpers."""
from __future__ import annotations

import pytest

from emberstream.config import get_settings
from emberstream.services.embeddings import NullEmbeddings, telemetry_to_text


def test_telemetry_to_text_is_deterministic() -> None:
    text_a = telemetry_to_text("s1", "temp", 42.0, "grid-A", "spike")
    text_b = telemetry_to_text("s1", "temp", 42.0, "grid-A", "spike")
    assert text_a == text_b


def test_telemetry_to_text_handles_missing_fields() -> None:
    text = telemetry_to_text("s1", "temp", 42.0, None, None)
    assert "location" not in text
    assert "notes" not in text


@pytest.mark.asyncio
async def test_null_embeddings_returns_correct_dim() -> None:
    embedder = NullEmbeddings(get_settings())
    vec = await embedder.embed("hello")
    assert len(vec) == get_settings().embedding_dim
    assert all(v == 0.0 for v in vec)
