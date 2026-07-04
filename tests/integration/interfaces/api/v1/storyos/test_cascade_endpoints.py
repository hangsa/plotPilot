"""Cascade endpoint integration tests (C1 1D stub)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_cascade_simulate_returns_response_envelope(client):
    """POST /cascade/simulate -> 200 + steps/summary keys present (1D stub)."""
    resp = client.post(
        "/api/v1/storyos/proj-1/cascade/simulate",
        json={
            "project_id": "proj-1",
            "trigger": "mystery_revealed",
            "source_asset_type": "mystery",
            "source_asset_id": "m-1",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "steps" in body
    assert "summary" in body


def test_cascade_simulate_validates_max_depth(client):
    """max_depth=10 -> 422 (spec section 4.2 locks MAX_CASCADE_DEPTH=3)."""
    resp = client.post(
        "/api/v1/storyos/proj-1/cascade/simulate",
        json={
            "project_id": "proj-1",
            "trigger": "mystery_revealed",
            "source_asset_type": "mystery",
            "source_asset_id": "m-1",
            "max_depth": 10,
        },
    )
    assert resp.status_code == 422


def test_cascade_replay_returns_501_or_200(client):
    """1D stub; 1E implements replay from bridge_log."""
    resp = client.post(
        "/api/v1/storyos/proj-1/cascade/replay/bridge-abc",
        json={"notes": "test"},
    )
    assert resp.status_code in (200, 501)


def test_cascade_history_returns_envelope(client):
    """GET /cascade/history?limit=50 -> 200 + {data, meta}."""
    resp = client.get("/api/v1/storyos/proj-1/cascade/history?limit=50")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "meta" in body
