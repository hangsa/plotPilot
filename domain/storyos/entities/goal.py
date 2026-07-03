"""Goal 实体（角色/情节目标，ProgressMarker T0-T9）。"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum

from domain.storyos.contracts import AssetStatus


class ProgressMarker(IntEnum):
    """目标进度标记（T0=起点 → T9=达成）。"""

    T0 = 0
    T1 = 1
    T2 = 2
    T3 = 3
    T4 = 4
    T5 = 5
    T6 = 6
    T7 = 7
    T8 = 8
    T9 = 9


@dataclass(frozen=True)
class Goal:
    """叙事目标实体。"""

    id: str
    novel_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    current_progress: ProgressMarker

    def __post_init__(self):
        if self.created_chapter < 1:
            raise ValueError("created_chapter must be >= 1")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")

    def advance(self, marker: ProgressMarker) -> "Goal":
        if marker.value <= self.current_progress.value:
            raise ValueError(
                f"new marker {marker.name} must be >= current {self.current_progress.name}"
            )
        return replace(self, current_progress=marker)