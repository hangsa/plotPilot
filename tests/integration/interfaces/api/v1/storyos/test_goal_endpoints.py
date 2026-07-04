"""Goal 5 CRUD endpoint integration tests (B1)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interfaces.api.v1.storyos.dependencies import reset_goal_adapter
from interfaces.api.v1.storyos.error_handlers import register_error_handlers
from interfaces.api.v1.storyos.router_registry import build_storyos_router


@pytest.fixture
def client():
    reset_goal_adapter()
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(build_storyos_router())
    return TestClient(app)


def test_list_goals_empty(client):
    resp = client.get("/api/v1/storyos/proj-new/goal")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0


def test_create_goal_minimal(client):
    resp = client.post(
        "/api/v1/storyos/proj-1/goal",
        json={
            "description": "Lin Yuan wants revenge",
            "created_chapter": 2,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["description"] == "Lin Yuan wants revenge"
    assert body["status"] == "active"
    # ProgressMarker.T0 = 0
    assert body["current_progress"] == 0
    assert body["created_chapter"] == 2
    assert body["project_id"] == "proj-1"
    assert "id" in body and body["id"]


def test_get_goal_by_id(client):
    create_resp = client.post(
        "/api/v1/storyos/proj-1/goal",
        json={"description": "x", "created_chapter": 1},
    )
    asset_id = create_resp.json()["id"]
    get_resp = client.get(f"/api/v1/storyos/proj-1/goal/{asset_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == asset_id


def test_get_goal_not_found_returns_envelope(client):
    resp = client.get("/api/v1/storyos/proj-1/goal/nonexistent-id")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "ASSET_NOT_FOUND"
    assert "nonexistent-id" in body["error"]["message"]


def test_update_goal_partial(client):
    create_resp = client.post(
        "/api/v1/storyos/proj-1/goal",
        json={"description": "x", "created_chapter": 1},
    )
    asset_id = create_resp.json()["id"]
    patch_resp = client.patch(
        f"/api/v1/storyos/proj-1/goal/{asset_id}",
        json={"status": "fulfilled"},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["status"] == "fulfilled"
    assert body["description"] == "x"  # unchanged


def test_delete_goal(client):
    create_resp = client.post(
        "/api/v1/storyos/proj-1/goal",
        json={"description": "x", "created_chapter": 1},
    )
    asset_id = create_resp.json()["id"]
    del_resp = client.delete(f"/api/v1/storyos/proj-1/goal/{asset_id}")
    assert del_resp.status_code == 204
    get_resp = client.get(f"/api/v1/storyos/proj-1/goal/{asset_id}")
    assert get_resp.status_code == 404


def test_list_goals_with_status_filter(client):
    client.post(
        "/api/v1/storyos/proj-1/goal",
        json={"description": "a", "created_chapter": 1},
    )
    client.post(
        "/api/v1/storyos/proj-1/goal",
        json={"description": "b", "created_chapter": 2, "status": "fulfilled"},
    )
    resp = client.get("/api/v1/storyos/proj-1/goal?status=fulfilled")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert all(g["status"] == "fulfilled" for g in data)
    assert len(data) == 1


def test_create_goal_rejects_invalid_status(client):
    resp = client.post(
        "/api/v1/storyos/proj-1/goal",
        json={
            "description": "x",
            "created_chapter": 1,
            "status": "bogus_value",
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
