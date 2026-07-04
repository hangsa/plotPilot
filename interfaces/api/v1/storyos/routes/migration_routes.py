"""Migration endpoints stub (A5) — handlers added by C3."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/storyos/{project_id}/migration", tags=["storyos-migration"])