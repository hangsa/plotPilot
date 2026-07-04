"""Cascade endpoints: simulate / replay / history (C1 1D stub)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from interfaces.api.v1.storyos.dependencies import get_cascade_service
from interfaces.api.v1.storyos.schemas.cascade_schemas import (
    CascadeReplayRequest,
    CascadeSimulateRequest,
)
from interfaces.api.v1.storyos.schemas.common_schemas import (
    ListResponseEnvelope,
    PaginationMeta,
)

router = APIRouter(prefix="/api/v1/storyos/{project_id}/cascade", tags=["storyos-cascade"])


@router.post("/simulate")
async def simulate_cascade(
    req: CascadeSimulateRequest,
    _service=Depends(get_cascade_service),
) -> dict:
    """1D stub: real cascade-from-trigger requires walking linked assets across
    8 registries (a 1E-grade feature). Returns 501 NOT_IMPLEMENTED rather than
    fabricated success data — frontend must surface this honestly until 1E
    wires the real CascadeService.
    """
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "cascade simulate is not implemented in 1D; see plan 1E",
            "details": {"phase": "1E", "scheduled": "2026-07"},
        },
    )


@router.post("/replay/{bridge_id}")
async def replay_cascade(
    bridge_id: str = Path(..., min_length=1),
    req: CascadeReplayRequest = CascadeReplayRequest(),
    _service=Depends(get_cascade_service),
) -> dict:
    """1D stub: cascade replay not implemented; 1E wires bridge_log reverse-replay."""
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "cascade replay is not implemented in 1D; see plan 1E",
        },
    )


@router.get("/history")
async def cascade_history(
    project_id: str = Path(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=500),
    _service=Depends(get_cascade_service),
) -> ListResponseEnvelope[dict]:
    """1D stub: history table added in 1E; return empty envelope for now."""
    return ListResponseEnvelope[dict](
        data=[],
        meta=PaginationMeta.compute(total=0, page=1, page_size=limit),
    )
