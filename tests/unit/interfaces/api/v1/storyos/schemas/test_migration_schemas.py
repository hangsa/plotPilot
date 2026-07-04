"""Migration 端点 DTO 测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.migration_schemas import (
    MigrationPreviewResponse,
    MigrationExecuteRequest,
    MigrationExecuteResponse,
    MigrationStatusResponse,
)
from domain.storyos.value_objects.format_error import FormatError


def test_migration_preview_response_fields():
    resp = MigrationPreviewResponse(
        total=100,
        scanned=100,
        migratable=80,
        skipped=15,
        invalid=5,
        sample_errors=[
            FormatError(
                code="MISSING_LINK",
                message="orphan foreshadowing",
                raw_text="...",
                char_position=0,
            )
        ],
    )
    assert resp.total == 100
    assert resp.scanned == 100
    assert resp.migratable == 80
    assert resp.skipped == 15
    assert resp.invalid == 5
    assert len(resp.sample_errors) == 1


def test_migration_execute_request_defaults():
    req = MigrationExecuteRequest()
    assert req.batch_size == 500
    assert req.dry_run is False


def test_migration_execute_request_validates_batch_size():
    with pytest.raises(ValidationError):
        MigrationExecuteRequest(batch_size=0)


def test_migration_execute_request_explicit_dry_run():
    req = MigrationExecuteRequest(batch_size=200, dry_run=True)
    assert req.batch_size == 200
    assert req.dry_run is True


def test_migration_execute_response_fields():
    resp = MigrationExecuteResponse(
        migration_id="mig-1",
        status="completed",
        batches_total=3,
        batches_done=3,
        errors=[],
    )
    assert resp.migration_id == "mig-1"
    assert resp.status == "completed"
    assert resp.batches_total == 3
    assert resp.batches_done == 3
    assert resp.errors == []


def test_migration_status_response_fields():
    resp = MigrationStatusResponse(
        migration_id="mig-1",
        status="running",
        progress_pct=66.6,
        eta_seconds=120,
    )
    assert resp.migration_id == "mig-1"
    assert resp.status == "running"
    assert resp.progress_pct == pytest.approx(66.6)
    assert resp.eta_seconds == 120


def test_migration_status_response_validates_progress_range():
    with pytest.raises(ValidationError):
        MigrationStatusResponse(
            migration_id="mig-1",
            status="running",
            progress_pct=150.0,  # 超出 0..100
        )
