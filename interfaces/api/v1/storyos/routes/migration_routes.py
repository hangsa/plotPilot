"""Migration 端点（1D 桩 → 1E 联通）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from interfaces.api.v1.storyos.dependencies import get_migration_service
from interfaces.api.v1.storyos.schemas.migration_schemas import (
    MigrationExecuteRequest,
    MigrationExecuteResponse,
    MigrationPreviewResponse,
)


router = APIRouter(prefix="/api/v1/storyos/{project_id}/migration", tags=["storyos-migration"])


@router.post(
    "/preview",
    response_model=MigrationPreviewResponse,
    summary="扫描旧 foreshadowing 表生成预览报告",
)
async def migration_preview(
    project_id: str = Path(..., min_length=1, max_length=64),
    service: ForeshadowingMigrationService = Depends(get_migration_service),
) -> MigrationPreviewResponse:
    """POST /api/v1/storyos/{project_id}/migration/preview。

    返回 5 元组报告：total / scanned / migratable / skipped / invalid + sample_errors。
    只读操作，不修改任何表。
    """
    report = service.scan(project_id)
    return MigrationPreviewResponse(
        total=report.total,
        scanned=report.scanned,
        migratable=report.migratable,
        skipped=report.skipped,
        invalid=report.invalid,
        sample_errors=[
            {"old_id": e.old_id, "code": e.code, "message": e.message}
            for e in report.sample_errors
        ],
    )


@router.post(
    "/execute",
    response_model=MigrationExecuteResponse,
    summary="执行 foreshadowing 单向迁移",
)
async def migration_execute(
    req: MigrationExecuteRequest,
    project_id: str = Path(..., min_length=1, max_length=64),
    service: ForeshadowingMigrationService = Depends(get_migration_service),
) -> MigrationExecuteResponse:
    """POST /api/v1/storyos/{project_id}/migration/execute。

    批量迁移旧表数据到 storyos_foreshadowing_v1。
    """
    result = service.execute(
        project_id, batch_size=req.batch_size, dry_run=req.dry_run,
    )
    return MigrationExecuteResponse(
        migration_id=result.migration_id,
        status=result.status,
        batches_total=result.batches_total,
        batches_done=result.batches_done,
        records_migrated=result.records_migrated,
        errors=result.errors,
    )