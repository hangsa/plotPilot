"""Promise 实体（叙事承诺）。"""
from __future__ import annotations

from dataclasses import dataclass, replace

from domain.storyos.contracts import AssetStatus


@dataclass(frozen=True)
class Promise:
    """作者向读者做出的承诺（伏笔的语义对偶）。"""

    id: str
    novel_id: str
    description: str
    made_in_chapter: int
    status: AssetStatus
    importance: int
    fulfilled_in_chapter: int | None = None

    def __post_init__(self):
        if self.made_in_chapter < 1:
            raise ValueError("made_in_chapter must be >= 1")
        if not 0 <= self.importance <= 100:
            raise ValueError(f"importance must be in [0, 100], got {self.importance}")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if self.status == AssetStatus.FULFILLED and self.fulfilled_in_chapter is None:
            raise ValueError("FULFILLED status requires fulfilled_in_chapter")
        if (
            self.fulfilled_in_chapter is not None
            and self.fulfilled_in_chapter < self.made_in_chapter
        ):
            raise ValueError("fulfilled_in_chapter must be >= made_in_chapter")

    def fulfill(self, chapter: int) -> "Promise":
        if self.status != AssetStatus.ACTIVE:
            raise ValueError(f"Cannot fulfill promise in status {self.status.value}")
        if chapter < self.made_in_chapter:
            raise ValueError(
                f"fulfill chapter {chapter} < made_in_chapter {self.made_in_chapter}"
            )
        return replace(self, status=AssetStatus.FULFILLED, fulfilled_in_chapter=chapter)