"""Validation tests for the Pydantic API schemas."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from emberstream.models import QueryIn, TelemetryIn


def test_telemetry_in_accepts_minimal_payload() -> None:
    t = TelemetryIn(sensor_id="s1", kind="temp", value=42.0)
    assert t.location is None
    assert t.notes is None


def test_telemetry_in_rejects_empty_sensor_id() -> None:
    with pytest.raises(ValidationError):
        TelemetryIn(sensor_id="", kind="temp", value=42.0)


def test_query_in_requires_min_length() -> None:
    with pytest.raises(ValidationError):
        QueryIn(question="hi")


def test_query_in_clamps_top_k() -> None:
    with pytest.raises(ValidationError):
        QueryIn(question="What is the trend?", top_k=0)
    with pytest.raises(ValidationError):
        QueryIn(question="What is the trend?", top_k=100)
