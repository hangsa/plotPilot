"""Migration 端点集成测试（1E 真实实现）。

1D 阶段这些端点为桩（501 NOT_IMPLEMENTED），1E 已接入
``ForeshadowingMigrationService`` 的真实实现：
- /preview    -> 200 (返回 5 元组扫描报告)
- /execute    -> 200 (返回 migration_id + 进度)
- /{id}/status -> 200 或 404 (audit 记录存在时 200，否则 404)
- /{id}/rollback -> 200 或 404 (同上)
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from application.storyos.services.migration_audit_service import (
    MigrationAuditService,
)
from application.storyos.value_objects.migration_preview_report import (
    MigrationPreviewReport,
)
from interfaces.api.v1.storyos import dependencies as deps
from interfaces.api.v1.storyos.error_handlers import register_error_handlers
from interfaces.api.v1.storyos.router_registry import build_storyos_router


@pytest.fixture
def client():
    """TestClient with mocked migration service so tests stay deterministic."""
    mock_service = MagicMock(spec=ForeshadowingMigrationService)
    mock_service.scan.return_value = MigrationPreviewReport(project_id="proj-1")
    mock_service.get_audit_record.return_value = None  # default -> 404
    deps._migration_service = mock_service  # bypass singleton cache
    try:
        app = FastAPI()
        register_error_handlers(app)
        app.include_router(build_storyos_router())
        yield TestClient(app)
    finally:
        deps._migration_service = None


def test_migration_preview_returns_200(client):
    """POST /migration/preview -> 200 + 5 元组报告."""
    resp = client.post("/api/v1/storyos/proj-1/migration/preview")
    assert resp.status_code == 200
    body = resp.json()
    for k in ("total", "scanned", "migratable", "skipped", "invalid", "sample_errors"):
        assert k in body


def test_migration_execute_returns_200(client):
    """POST /migration/execute -> 200 + migration_id."""
    mock_result = MagicMock()
    mock_result.migration_id = "mig-test-001"
    mock_result.status = "completed"
    mock_result.batches_total = 1
    mock_result.batches_done = 1
    mock_result.records_migrated = 0
    mock_result.errors = []
    deps._migration_service.execute.return_value = mock_result
    resp = client.post(
        "/api/v1/storyos/proj-1/migration/execute",
        json={"batch_size": 500, "dry_run": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["migration_id"] == "mig-test-001"
    assert body["status"] == "completed"


def test_migration_status_returns_404_when_unknown(client):
    """GET /migration/{id}/status -> 404 (audit 记录缺失)."""
    resp = client.get("/api/v1/storyos/proj-1/migration/mig-abc/status")
    assert resp.status_code == 404


def test_migration_status_returns_200_when_known(client):
    """GET /migration/{id}/status -> 200 (audit 记录命中)."""
    mock_record = MagicMock()
    mock_record.batches_total = 10
    mock_record.batches_done = 4
    mock_record.status = "in_progress"
    deps._migration_service.get_audit_record.return_value = mock_record
    resp = client.get("/api/v1/storyos/proj-1/migration/mig-known/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["progress_pct"] == 40
    assert body["status"] == "in_progress"


def test_migration_rollback_returns_404_when_unknown(client):
    """POST /migration/{id}/rollback -> 404."""
    mock_result = MagicMock()
    mock_result.status = "not_found"
    deps._migration_service.rollback.return_value = mock_result
    resp = client.post("/api/v1/storyos/proj-1/migration/mig-abc/rollback")
    assert resp.status_code == 404


def test_migration_endpoints_registered_in_schema(client):
    """所有 4 个端点必须在 OpenAPI schema 可见。"""
    resp = client.get("/openapi.json")
    schema = resp.json()
    paths = schema["paths"]
    assert "/api/v1/storyos/{project_id}/migration/preview" in paths
    assert "/api/v1/storyos/{project_id}/migration/execute" in paths
    assert "/api/v1/storyos/{project_id}/migration/{migration_id}/status" in paths
    assert "/api/v1/storyos/{project_id}/migration/{migration_id}/rollback" in paths
