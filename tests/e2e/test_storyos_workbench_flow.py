"""E2E: StoryOS workbench happy path — create assets, list, simulate (501 stub),
query history, check health.

1D scope: the cascade simulate endpoint is a 1D stub returning 501
NOT_IMPLEMENTED (1E wires the real CascadeService). All other endpoints
should return 2xx with real CRUD data. This test verifies the end-to-end
plumbing works; full happy-path simulation lands in 1E.
"""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interfaces.api.v1.storyos.dependencies import reset_conflict_adapter
from interfaces.api.v1.storyos.router_registry import build_storyos_router


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Minimal FastAPI TestClient that mounts only storyos routers,
    bypassing interfaces.main:app (PEP 604 union syntax incompatible
    with Python 3.9.6).
    """
    reset_conflict_adapter()
    app = FastAPI()
    # build_storyos_router() returns an APIRouter with all 40 CRUD
    # endpoints + cascade/sflog/migration/health mounted under
    # /api/v1/storyos/{project_id}.
    app.include_router(build_storyos_router())
    yield TestClient(app)


def test_e2e_storyos_workbench_flow(client):
    # 1. Create two conflicts.
    # ConflictIntensity is an IntEnum (LOW=1..CRITICAL=4); values 2 and 4
    # exercise the medium / critical tier.
    cf1 = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={"description": "a", "created_chapter": 1, "intensity": 2},
    ).json()
    cf2 = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={"description": "b", "created_chapter": 2, "intensity": 4},
    ).json()
    assert cf1["status"] == "active"
    assert cf2["status"] == "active"
    assert cf1["id"] != cf2["id"]  # distinct IDs — catches generator collisions

    # 2. List conflicts.
    list_resp = client.get("/api/v1/storyos/proj-1/conflict")
    assert list_resp.status_code == 200
    body = list_resp.json()
    # ListResponseEnvelope shape: {data: [...], meta: {total: N, ...}}
    total = body.get("meta", {}).get("total", len(body.get("data", [])))
    assert total >= 2

    # 3. Cascade simulate (1D stub returns 501; 1E will return 200).
    sim_resp = client.post(
        "/api/v1/storyos/proj-1/cascade/simulate",
        json={
            "project_id": "proj-1",
            "trigger": "conflict_resolved",
            "source_asset_type": "conflict",
            "source_asset_id": cf1["id"],
            "proposed_new_status": "resolved",
        },
    )
    # 1D reality: simulate returns 501 NOT_IMPLEMENTED.
    # 1E expectation: returns 200 with CascadeSimulateResponse.
    assert sim_resp.status_code in (200, 501), (
        f"cascade simulate should return 200 (1E) or 501 (1D stub); "
        f"got {sim_resp.status_code}: {sim_resp.text}"
    )

    # 4. Cascade history (always 200 in 1D, returns empty envelope).
    hist_resp = client.get("/api/v1/storyos/proj-1/cascade/history?limit=10")
    assert hist_resp.status_code == 200
    hist_body = hist_resp.json()
    # Assert the envelope shape, not just the status — a fallback route
    # returning an empty 200 must not silently pass.
    assert isinstance(hist_body.get("data"), list)
    assert isinstance(hist_body.get("meta", {}).get("total"), int)

    # 5. Project-scoped health (verify endpoint exists and returns valid shape).
    health_resp = client.get("/api/v1/storyos/proj-1/health")
    assert health_resp.status_code == 200
    h_body = health_resp.json()
    # HealthResponse shape: {status, components, timestamp}.
    assert h_body.get("status") in ("ok", "degraded"), (
        f"unexpected health status: {h_body}"
    )

    # 6. SFLog reparse (1D stub returns 200 with zero counts).
    sflog_resp = client.post("/api/v1/storyos/proj-1/sflog/reparse/5")
    assert sflog_resp.status_code == 200
    sflog_body = sflog_resp.json()
    assert sflog_body["chapter_id"] == 5
    assert sflog_body["parsed_count"] == 0  # 1D stub

    # 7. Cleanup (delete one conflict; keep one for state-leak visibility).
    del_resp = client.delete(f"/api/v1/storyos/proj-1/conflict/{cf2['id']}")
    assert del_resp.status_code in (200, 204)