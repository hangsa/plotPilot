"""SFLog endpoints stub (A5) — handlers added by C2."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/storyos/{project_id}/sflog", tags=["storyos-sflog"])