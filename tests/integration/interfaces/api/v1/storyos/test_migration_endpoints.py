"""Migration 端点集成测试（C3 1D 桩）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_migration_preview_returns_501(client):
    """POST /migration/preview -> 501 + ErrorResponse envelope."""
    resp = client.post("/api/v1/storyos/proj-1/migration/preview")
    assert resp.status_code == 501
    body = resp.json()
    assert body["error"]["code"] == "NOT_IMPLEMENTED"
    assert "Phase 1E" in body["error"]["message"]


def test_migration_execute_returns_501(client):
    """POST /migration/execute with body -> 501 + ErrorResponse envelope."""
    resp = client.post(
        "/api/v1/storyos/proj-1/migration/execute",
        json={"batch_size": 500, "dry_run": False},
    )
    assert resp.status_code == 501
    body = resp.json()
    assert body["error"]["code"] == "NOT_IMPLEMENTED"
    assert "Phase 1E" in body["error"]["message"]


def test_migration_status_returns_501(client):
    """GET /migration/{id}/status -> 501 + ErrorResponse envelope."""
    resp = client.get("/api/v1/storyos/proj-1/migration/mig-abc/status")
    assert resp.status_code == 501
    body = resp.json()
    assert body["error"]["code"] == "NOT_IMPLEMENTED"
    assert "Phase 1E" in body["error"]["message"]


def test_migration_rollback_returns_501(client):
    """POST /migration/{id}/rollback -> 501 + ErrorResponse envelope."""
    resp = client.post("/api/v1/storyos/proj-1/migration/mig-abc/rollback")
    assert resp.status_code == 501
    body = resp.json()
    assert body["error"]["code"] == "NOT_IMPLEMENTED"
    assert "Phase 1E" in body["error"]["message"]


def test_migration_endpoints_registered_in_schema(client):
    """即使 1D 桩，所有 4 个端点必须在 OpenAPI schema 可见。"""
    resp = client.get("/openapi.json")
    schema = resp.json()
    paths = schema["paths"]
    assert "/api/v1/storyos/{project_id}/migration/preview" in paths
    assert "/api/v1/storyos/{project_id}/migration/execute" in paths
    assert "/api/v1/storyos/{project_id}/migration/{id}/status" in paths
    assert "/api/v1/storyos/{project_id}/migration/{id}/rollback" in paths
