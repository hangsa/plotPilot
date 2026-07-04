"""Migration endpoints (C3 1D stub -> 1E real wiring).

1D phase: routes registered, all return 501 NOT_IMPLEMENTED.
1E phase: replace handlers with ForeshadowingMigrationService logic.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path

from interfaces.api.v1.storyos.dependencies import get_migration_service
from interfaces.api.v1.storyos.schemas.migration_schemas import MigrationExecuteRequest

router = APIRouter(prefix="/api/v1/storyos/{project_id}/migration", tags=["storyos-migration"])


_NOT_IMPLEMENTED_501 = {
    "code": "NOT_IMPLEMENTED",
    "message": "Migration endpoint will be implemented in Phase 1E",
    "details": {"phase": "1E", "scheduled": "2026-07"},
}


@router.post("/preview")
async def migration_preview(
    project_id: str = Path(..., min_length=1),
    _service=Depends(get_migration_service),
) -> dict:
    """1D stub: scan legacy foreshadowing rows and preview migratable data.

    1E wiring: delegates to ``ForeshadowingMigrationService.scan()``.
    """
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_501)


@router.post("/execute")
async def migration_execute(
    req: MigrationExecuteRequest,
    project_id: str = Path(..., min_length=1),
    _service=Depends(get_migration_service),
) -> dict:
    """1D stub: batched migration execution with resume support.

    1E wiring: delegates to ``ForeshadowingMigrationService.execute()``.
    """
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_501)


@router.get("/{id}/status")
async def migration_status(
    project_id: str = Path(..., min_length=1),
    id: str = Path(..., min_length=1),
    _service=Depends(get_migration_service),
) -> dict:
    """1D stub: progress + ETA for a running migration.

    1E wiring: delegates to ``ForeshadowingMigrationService.status()``.
    """
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_501)


@router.post("/{id}/rollback")
async def migration_rollback(
    project_id: str = Path(..., min_length=1),
    id: str = Path(..., min_length=1),
    _service=Depends(get_migration_service),
) -> dict:
    """1D stub: revert a completed migration.

    1E wiring: delegates to ``ForeshadowingMigrationService.rollback()``.
    """
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_501)
