"""Smoke test for the OpenAPI schema and route surface."""
from __future__ import annotations


def test_openapi_lists_expected_routes(app) -> None:
    schema = app.openapi()
    paths = set(schema["paths"].keys())
    assert "/telemetry" in paths
    assert "/query" in paths
    # /ws/telemetry is a websocket route and not part of OpenAPI by design.


def test_health_endpoint_exists(app) -> None:
    # Health route is excluded from schema; just confirm route is registered.
    routes = {r.path for r in app.routes}
    assert "/health" in routes
