"""Health + Metrics endpoints (C4 1D stub)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint_returns_ok(client):
    """GET /health -> 200 + 4 components."""
    resp = client.get("/api/v1/storyos/proj-1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded", "down")
    assert "components" in body
    expected = {"registry", "cascade", "sflog_parser", "bridge"}
    assert expected.issubset(body["components"].keys())


def test_metrics_endpoint_returns_storyos_metrics(client):
    """GET /metrics -> 200 + spec 5.2 6 metrics."""
    resp = client.get("/api/v1/storyos/proj-1/metrics")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "sflog_format_compliance_rate",
        "sflog_predeclared_match_rate",
        "cascade_block_rate",
        "bridge_failure_rate",
        "avg_cascade_depth",
        "force_pass_count_per_chapter",
    ):
        assert key in body, f"missing {key}"
