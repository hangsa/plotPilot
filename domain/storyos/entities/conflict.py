"""Conflict 实体（spec §3.1 列出，§4.2 cascade 规则之一）。"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum


from domain.storyos.contracts import AssetStatus


class ConflictIntensity(IntEnum):
    """冲突强度（数值越大越剧烈，cascade +30 一档）。"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class Conflict:
    """冲突实体：角色/阵营/事件 之间的张力。"""

    id: str
    novel_id: str
    description: str
    intensity: ConflictIntensity
    status: AssetStatus
    involved_characters: tuple[str, ...]
    created_chapter: int
    linked_conflicts: tuple[str, ...] = ()

    def __post_init__(self):
        if self.created_chapter < 1:
            raise ValueError("created_chapter must be >= 1")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.novel_id or not self.novel_id.strip():
            raise ValueError("novel_id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if not self.involved_characters:
            raise ValueError("involved_characters must not be empty")

    def escalate(self) -> "Conflict":
        """提升一档 intensity（LOW→MEDIUM→HIGH→CRITICAL）。"""
        levels = list(ConflictIntensity)
        idx = levels.index(self.intensity)
        if idx == len(levels) - 1:
            raise ValueError(
                f"Conflict {self.id} is already CRITICAL; cannot escalate"
            )
        return replace(self, intensity=levels[idx + 1])
