"""Shared pytest fixtures."""
from __future__ import annotations

import pytest

from emberstream.main import create_app


@pytest.fixture
def app():
    """A fresh FastAPI app instance for tests.

    The lifespan (DB / Redis connections) is not triggered here, so unit
    tests can introspect routes, schemas, and dependencies without needing
    any backing services.
    """
    return create_app()
