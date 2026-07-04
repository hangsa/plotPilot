"""Migration endpoints integration tests (1E 联通 1D 501 stubs -> real handlers).

Note: uses minimal-FastAPI pattern (C1 fix) — interfaces.main:app has Python
3.10+/3.11+ tech debt (PEP 604 union syntax) incompatible with Python 3.9.6,
so we mount only the storyos subrouters on a fresh FastAPI app with the same
error handlers as the production app, ensuring 422/404 responses share the
StoryOS {error: {code, message}} envelope.

Note: FastAPI's Depends() captures the dependency callable at function def
time, so patching the module attribute does NOT propagate to the captured
reference. We instead use ``app.dependency_overrides`` (FastAPI-supported
mechanism) via the ``_migration_app`` fixture which exposes both the app
and a stand-in for ``get_migration_service`` that tests can configure.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interfaces.api.v1.storyos.dependencies import get_migration_service
from interfaces.api.v1.storyos.error_handlers import register_error_handlers
from interfaces.api.v1.storyos.router_registry import build_storyos_router
from application.storyos.value_objects.migration_preview_report import (
    MigrationPreviewReport,
)
from application.storyos.services.foreshadowing_migration_service import (
    MigrationExecuteResult,
)


@pytest.fixture
def _migration_app():
    """Build a minimal FastAPI app and a stand-in for the migration service.

    Returns ``(client, mock_migration_service)`` where ``client`` is a
    TestClient and ``mock_migration_service`` is a small object whose
    ``.return_value`` tests can assign a MagicMock to. The stand-in is
    registered as a FastAPI ``dependency_overrides`` entry so FastAPI's
    request-time dependency resolver uses it instead of the original
    ``get_migration_service``.
    """
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(build_storyos_router())

    holder = {"service": None}

    async def _override() -> object:
        return holder["service"]

    app.dependency_overrides[get_migration_service] = _override

    class _Mock:
        def __init__(self) -> None:
            self._holder = holder

        @property
        def return_value(self) -> object:
            return self._holder["service"]

        @return_value.setter
        def return_value(self, value: object) -> None:
            self._holder["service"] = value

    return TestClient(app), _Mock()


@pytest.fixture
def client(_migration_app):
    """TestClient bound to a minimal FastAPI app mounting storyos routers."""
    return _migration_app[0]


@pytest.fixture
def mock_migration_service(_migration_app):
    """Stand-in for the migration service registered via dependency_overrides."""
    return _migration_app[1]


# ─── D1 Tests (replace 1D 501 stubs) ─────────────────────────────────


def test_preview_returns_5_tuple_report(client, mock_migration_service):
    """POST /migration/preview 返回 MigrationPreviewResponse 5 元组。"""
    service = MagicMock()
    service.scan.return_value = MigrationPreviewReport(
        project_id="proj-1", total=100, scanned=100,
        migratable=85, skipped=10, invalid=5,
        sample_errors=[],
    )
    mock_migration_service.return_value = service

    resp = client.post("/api/v1/storyos/proj-1/migration/preview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 100
    assert body["migratable"] == 85
    assert body["invalid"] == 5
    service.scan.assert_called_once_with("proj-1")


def test_preview_returns_empty_report_for_new_project(client, mock_migration_service):
    service = MagicMock()
    service.scan.return_value = MigrationPreviewReport(project_id="proj-empty")
    mock_migration_service.return_value = service
    resp = client.post("/api/v1/storyos/proj-empty/migration/preview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["migratable"] == 0


def test_execute_calls_service_with_request_params(client, mock_migration_service):
    """POST /migration/execute 接收 batch_size + dry_run 参数。"""
    service = MagicMock()
    service.execute.return_value = MigrationExecuteResult(
        migration_id="mig-1", status="completed",
        batches_total=2, batches_done=2, records_migrated=100, errors=[],
    )
    mock_migration_service.return_value = service

    resp = client.post(
        "/api/v1/storyos/proj-1/migration/execute",
        json={"batch_size": 200, "dry_run": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["migration_id"] == "mig-1"
    assert body["status"] == "completed"
    assert body["batches_total"] == 2
    service.execute.assert_called_once_with("proj-1", batch_size=200, dry_run=False)


def test_execute_default_batch_size_is_500(client, mock_migration_service):
    """MigrationExecuteRequest 默认 batch_size=500。"""
    service = MagicMock()
    service.execute.return_value = MigrationExecuteResult(
        migration_id="mig-1", status="completed",
        batches_total=1, batches_done=1, records_migrated=10, errors=[],
    )
    mock_migration_service.return_value = service

    resp = client.post(
        "/api/v1/storyos/proj-1/migration/execute",
        json={"dry_run": False},
    )
    service.execute.assert_called_once_with("proj-1", batch_size=500, dry_run=False)


def test_execute_dry_run_returns_dry_run_status(client, mock_migration_service):
    service = MagicMock()
    service.execute.return_value = MigrationExecuteResult(
        migration_id="dry-run", status="dry_run",
        batches_total=2, batches_done=0, records_migrated=0, errors=[],
    )
    mock_migration_service.return_value = service
    resp = client.post(
        "/api/v1/storyos/proj-1/migration/execute",
        json={"batch_size": 500, "dry_run": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    assert body["records_migrated"] == 0


def test_execute_invalid_batch_size_returns_422(client, mock_migration_service):
    """batch_size <= 0 时 FastAPI 422 校验失败。"""
    resp = client.post(
        "/api/v1/storyos/proj-1/migration/execute",
        json={"batch_size": 0, "dry_run": False},
    )
    assert resp.status_code == 422


def test_endpoints_still_in_openapi_schema(client):
    """即使替换为真实实现，端点仍在 OpenAPI 中可见。"""
    resp = client.get("/openapi.json")
    schema = resp.json()
    paths = schema["paths"]
    assert "/api/v1/storyos/{project_id}/migration/preview" in paths
    assert "/api/v1/storyos/{project_id}/migration/execute" in paths