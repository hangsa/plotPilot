"""Migration 端点（1D 桩 → 1E 联通）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from interfaces.api.v1.storyos.dependencies import get_migration_service
from interfaces.api.v1.storyos.schemas.migration_schemas import (
    MigrationExecuteRequest,
    MigrationExecuteResponse,
    MigrationPreviewResponse,
    MigrationStatusResponse,
    RollbackResponse,
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


@router.get(
    "/{migration_id}/status",
    response_model=MigrationStatusResponse,
    summary="查询迁移进度",
)
async def migration_status(
    project_id: str = Path(..., min_length=1, max_length=64),
    migration_id: str = Path(..., min_length=1, max_length=64),
    service: ForeshadowingMigrationService = Depends(get_migration_service),
) -> MigrationStatusResponse:
    """GET /api/v1/storyos/{project_id}/migration/{migration_id}/status。

    返回当前进度 + 错误列表 + ETA（粗略估算）。
    """
    record = service.get_audit_record(migration_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "MIGRATION_NOT_FOUND", "message": f"migration {migration_id} not found"},
        )
    progress_pct = (
        int(record.batches_done / record.batches_total * 100)
        if record.batches_total > 0 else 0
    )
    # ETA 粗略估算：剩余 batches * 平均每批 200ms
    eta_seconds = int((record.batches_total - record.batches_done) * 0.2)
    return MigrationStatusResponse(
        migration_id=migration_id,
        status=record.status,
        progress_pct=progress_pct,
        eta_seconds=eta_seconds,
    )


@router.post(
    "/{migration_id}/rollback",
    response_model=RollbackResponse,
    summary="回滚单条迁移批次",
)
async def migration_rollback(
    project_id: str = Path(..., min_length=1, max_length=64),
    migration_id: str = Path(..., min_length=1, max_length=64),
    service: ForeshadowingMigrationService = Depends(get_migration_service),
) -> RollbackResponse:
    """POST /api/v1/storyos/{project_id}/migration/{migration_id}/rollback。

    只删除新表数据，旧表不动（spec Q8）。
    """
    result = service.rollback(migration_id)
    if result.status == "not_found":
        raise HTTPException(
            status_code=404,
            detail={"code": "MIGRATION_NOT_FOUND", "message": f"migration {migration_id} not found"},
        )
    return RollbackResponse(
        migration_id=result.migration_id,
        records_deleted=result.records_deleted,
        status=result.status,
    )