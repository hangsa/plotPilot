"""Mystery + Clue 实体（sub-spec §3 锁定字段）。"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from domain.storyos.contracts import AssetStatus


class ClueCategory(str, Enum):
    """Clue 语义分类（与 RevealedClueItem.category 对齐）。"""

    TRUTH = "truth"
    RELATIONSHIP = "relationship"
    IDENTITY = "identity"
    ABILITY = "ability"
    OTHER = "other"


@dataclass(frozen=True)
class Clue:
    """Mystery 的组成成分。"""

    id: str
    mystery_id: str
    description: str
    source_chapter: int
    source_location: str
    category: ClueCategory = ClueCategory.TRUTH
    status: AssetStatus = AssetStatus.PLANTED
    discovered_in_chapter: int | None = None
    invalidated_in_chapter: int | None = None

    def __post_init__(self):
        if self.source_chapter < 1:
            raise ValueError("source_chapter must be >= 1")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if not self.source_location or not self.source_location.strip():
            raise ValueError("source_location cannot be empty")
        if self.discovered_in_chapter is not None and self.discovered_in_chapter < self.source_chapter:
            raise ValueError("discovered_in_chapter must be >= source_chapter")
        if self.invalidated_in_chapter is not None and self.invalidated_in_chapter < self.source_chapter:
            raise ValueError("invalidated_in_chapter must be >= source_chapter")
        if self.status == AssetStatus.REVEALED and self.discovered_in_chapter is None:
            raise ValueError("REVEALED status requires discovered_in_chapter")
        if self.status == AssetStatus.DEAD and self.invalidated_in_chapter is None:
            raise ValueError("DEAD status requires invalidated_in_chapter")

    def discover(self, chapter: int) -> "Clue":
        if self.status != AssetStatus.PLANTED:
            raise ValueError(f"Cannot discover clue in status {self.status.value}")
        if chapter < self.source_chapter:
            raise ValueError(
                f"discover chapter {chapter} < source_chapter {self.source_chapter}"
            )
        return replace(
            self, status=AssetStatus.REVEALED, discovered_in_chapter=chapter,
        )

    def invalidate(self, chapter: int) -> "Clue":
        if self.status not in (AssetStatus.PLANTED, AssetStatus.REVEALED):
            raise ValueError(f"Cannot invalidate clue in status {self.status.value}")
        return replace(
            self, status=AssetStatus.DEAD, invalidated_in_chapter=chapter,
        )


@dataclass(frozen=True)
class Mystery:
    """悬疑/谜团实体（包含多条 Clue）。"""

    id: str
    novel_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    clues: tuple[Clue, ...] = ()
    related_mystery: str | None = None

    def __post_init__(self):
        if self.created_chapter < 1:
            raise ValueError("created_chapter must be >= 1")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")

    def add_clue(self, clue: Clue) -> "Mystery":
        if clue.mystery_id != self.id:
            raise ValueError(
                f"clue.mystery_id={clue.mystery_id} != mystery.id={self.id}"
            )
        return replace(self, clues=self.clues + (clue,))