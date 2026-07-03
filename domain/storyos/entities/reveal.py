"""Reveal 实体（叙世揭示）。"""
from __future__ import annotations

from dataclasses import dataclass, replace

from domain.storyos.contracts import AssetStatus


@dataclass(frozen=True)
class Reveal:
    """叙事揭示（HIDDEN → REVEALED）。"""

    id: str
    novel_id: str
    content: str
    status: AssetStatus
    related_mystery: str | None
    linked_to_conflict: str | None = None
    revealed_in_chapter: int | None = None

    def __post_init__(self):
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be empty")
        if self.status == AssetStatus.REVEALED and self.revealed_in_chapter is None:
            raise ValueError("REVEALED status requires revealed_in_chapter")

    def reveal(self, chapter: int) -> "Reveal":
        if self.status != AssetStatus.HIDDEN:
            raise ValueError(f"Cannot reveal in status {self.status.value}")
        if chapter < 1:
            raise ValueError(f"chapter must be >= 1, got {chapter}")
        return replace(self, status=AssetStatus.REVEALED, revealed_in_chapter=chapter)
