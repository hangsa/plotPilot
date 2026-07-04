"""Health + Metrics endpoints (C4 1D stub)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from interfaces.api.v1.storyos.dependencies import (
    get_health_service,
    get_metrics_service,
)

router = APIRouter(prefix="/api/v1/storyos/{project_id}", tags=["storyos-health"])


@router.get("/health")
async def health(
    _service=Depends(get_health_service),
) -> dict:
    """Aggregate health of 4 StoryOS subsystems (1D stub returns ok)."""
    components = {
        "registry": {"status": "ok"},
        "cascade": {"status": "ok"},
        "sflog_parser": {"status": "ok"},
        "bridge": {"status": "ok"},
    }
    return {
        "status": "ok",
        "components": components,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics")
async def metrics(
    _service=Depends(get_metrics_service),
) -> dict:
    """Return spec 5.2 StoryOS metrics (1D stub zeros; 1E computes real values)."""
    return {
        "sflog_format_compliance_rate": 0.0,
        "sflog_predeclared_match_rate": 0.0,
        "cascade_block_rate": 0.0,
        "bridge_failure_rate": 0.0,
        "avg_cascade_depth": 0.0,
        "force_pass_count_per_chapter": 0.0,
    }
