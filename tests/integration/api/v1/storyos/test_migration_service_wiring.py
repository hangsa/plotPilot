"""Migration service wiring integration test (1E C1 fix).

Validates that ``interfaces.api.v1.storyos.dependencies.get_migration_service``
returns a real :class:`ForeshadowingMigrationService` instance, not the 1D
``return None`` stub.

Before the C1 fix this test FAILS with::

    AttributeError: 'NoneType' object has no attribute 'scan'

After the fix the test exercises the real production schema
(``storyos_migration_log_v1`` + legacy ``foreshadows`` table) on a temporary
SQLite DB and POSTs through the minimal-FastAPI app pattern.
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from application.storyos.migration.migration_log_repository import (
    MigrationLogRepository,
)
from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingAdapter,
)
from application.storyos.migration.new_foreshadowing_writer import (
    NewForeshadowingWriter,
)
from application.storyos.services.migration_audit_service import (
    MigrationAuditService,
)
from infrastructure.persistence.database.connection import DatabaseConnection
import interfaces.api.v1.storyos.dependencies as deps_module
from interfaces.api.v1.storyos.dependencies import (
    get_migration_service,
    reset_migration_service,
)
from interfaces.api.v1.storyos.error_handlers import register_error_handlers
from interfaces.api.v1.storyos.router_registry import build_storyos_router


_LEGACY_SCHEMA = """
CREATE TABLE IF NOT EXISTS foreshadows (
    id TEXT PRIMARY KEY, novel_id TEXT NOT NULL,
    description TEXT NOT NULL, planted_chapter INTEGER NOT NULL,
    due_chapter INTEGER, resolved_chapter INTEGER,
    status TEXT NOT NULL DEFAULT 'planted',
    importance INTEGER NOT NULL DEFAULT 2,
    subtext_type TEXT
);
"""

_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS storyos_migration_log_v1 (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    migration_type TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    old_ids TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_migration_log_project_type
    ON storyos_migration_log_v1(project_id, migration_type, status);
"""


@pytest.fixture
def temp_db_path(monkeypatch):
    """Create a temporary SQLite DB and patch ``dependencies.get_database``
    so the migration factory resolves the temp DB instead of the production
    ``data/plotpilot.db``.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript(_LEGACY_SCHEMA + _LOG_SCHEMA)
    conn.commit()
    conn.close()

    # Build a DatabaseConnection for this path. We bypass ``get_database``
    # entirely — the factory binds ``db = get_database()`` at construction
    # time, so we patch the symbol the factory sees.
    test_db = DatabaseConnection(path)

    def patched_get_database(db_path=None):
        return test_db

    monkeypatch.setattr(deps_module, "get_database", patched_get_database)
    # Reset singleton so the next dependency call rebuilds against patched DB.
    reset_migration_service()
    yield path

    # Final cleanup — restore singleton state.
    reset_migration_service()
    try:
        os.unlink(path)
    except OSError:
        pass


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_get_migration_service_returns_real_instance(temp_db_path):
    """The DI factory must return a real ``ForeshadowingMigrationService``.

    Before the C1 fix this resolves to ``None`` (the 1D stub). After the
    fix the singleton is constructed from production adapters pointing at
    the test-only DB path.
    """
    service = _run_async(get_migration_service())

    assert service is not None, "get_migration_service returned None (1D stub leaked)"
    assert isinstance(service, ForeshadowingMigrationService)
    # Confirm DI wired all four collaborators.
    assert isinstance(service._legacy, LegacyForeshadowingAdapter)
    assert isinstance(service._log_repo, MigrationLogRepository)
    assert isinstance(service._new_writer, NewForeshadowingWriter)
    assert isinstance(service._audit, MigrationAuditService)


def test_reset_migration_service_clears_singleton(temp_db_path):
    """``reset_migration_service`` must clear the cached singleton."""
    first = _run_async(get_migration_service())
    second = _run_async(get_migration_service())
    assert first is second  # cached

    reset_migration_service()
    third = _run_async(get_migration_service())
    # After reset, a new instance is constructed.
    assert third is not first


def test_preview_does_not_crash_with_attribute_error(temp_db_path):
    """POST /preview through FastAPI must NOT raise ``AttributeError``.

    Validates the full production path: FastAPI dependency resolution
    -> real ``ForeshadowingMigrationService.scan()`` -> 5-tuple response.

    With an empty legacy ``foreshadows`` table and an empty
    ``storyos_migration_log_v1`` (no committed rows), all numeric counters
    are zero and the response is a valid 200.
    """
    # Sanity-check schema exists on the temp DB.
    conn = sqlite3.connect(temp_db_path)
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = {row[0] for row in rows}
    conn.close()
    assert "foreshadows" in table_names
    assert "storyos_migration_log_v1" in table_names

    # The fixture already reset the singleton to ensure the patched DB is
    # picked up. Now build a FastAPI app without dependency_overrides so
    # the request goes through the real factory.
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(build_storyos_router())
    app.dependency_overrides.clear()

    client = TestClient(app)
    resp = client.post("/api/v1/storyos/proj-empty/migration/preview")
    assert resp.status_code == 200, (
        f"expected 200 from preview against empty DB, got {resp.status_code}: "
        f"{resp.text}"
    )
    body = resp.json()
    # 5-tuple: total / scanned / migratable / skipped / invalid.
    for key in ("total", "scanned", "migratable", "skipped", "invalid"):
        assert key in body, f"missing field '{key}' in {body}"
        assert isinstance(body[key], int)
        assert body[key] >= 0

