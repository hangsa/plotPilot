"""Health + Metrics endpoints stub (A5) — handlers added by C4."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/storyos/{project_id}", tags=["storyos-health"])