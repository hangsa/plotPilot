"""Foreshadowing 实体（新位置；旧位置 domain/novel/value_objects/foreshadowing.py 保留至 Phase 2）。

spec 附录 C 锁定旧→新状态映射：planted→PLANTED, resolved→REVEALED, abandoned→DEAD。
1A 不删除旧代码；1E 迁移脚本会引用本文件。
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from domain.novel.value_objects.foreshadowing import ImportanceLevel
from domain.storyos.contracts import AssetStatus


@dataclass(frozen=True)
class Foreshadowing:
    """伏笔实体（统一真相源，状态用 AssetStatus）。"""

    id: str
    novel_id: str
    description: str
    importance: ImportanceLevel
    status: AssetStatus
    planted_in_chapter: int
    suggested_resolve_chapter: int | None = None
    resolved_in_chapter: int | None = None

    def __post_init__(self):
        # dataclass 不做类型校验；当调用方传入裸 int（如 999）时，Python 不会
        # 自动调用 ImportanceLevel(value)，需手动验证 ImportanceLevel 成员身份。
        if not isinstance(self.importance, ImportanceLevel):
            raise ValueError(
                f"importance must be a valid ImportanceLevel member, got {self.importance!r}"
            )
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.novel_id or not self.novel_id.strip():
            raise ValueError("novel_id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if self.planted_in_chapter < 1:
            raise ValueError("planted_in_chapter must be >= 1")
        if self.status == AssetStatus.REVEALED and self.resolved_in_chapter is None:
            raise ValueError("REVEALED status requires resolved_in_chapter")
        if self.suggested_resolve_chapter is not None and self.suggested_resolve_chapter < 1:
            raise ValueError("suggested_resolve_chapter must be >= 1")
        if self.resolved_in_chapter is not None and self.resolved_in_chapter < 1:
            raise ValueError("resolved_in_chapter must be >= 1")
        if (
            self.resolved_in_chapter is not None
            and self.resolved_in_chapter < self.planted_in_chapter
        ):
            raise ValueError("resolved_in_chapter must be >= planted_in_chapter")
        if (
            self.suggested_resolve_chapter is not None
            and self.suggested_resolve_chapter < self.planted_in_chapter
        ):
            raise ValueError("suggested_resolve_chapter must be >= planted_in_chapter")

    def resolve(self, chapter: int) -> "Foreshadowing":
        if self.status != AssetStatus.PLANTED:
            raise ValueError(f"Cannot resolve foreshadowing in status {self.status.value}")
        if chapter < self.planted_in_chapter:
            raise ValueError(
                f"resolve chapter {chapter} < planted_in_chapter {self.planted_in_chapter}"
            )
        return replace(
            self, status=AssetStatus.REVEALED, resolved_in_chapter=chapter,
        )

    def abandon(self, chapter: int) -> "Foreshadowing":
        if self.status not in (AssetStatus.PLANTED, AssetStatus.REVEALED):
            raise ValueError(f"Cannot abandon foreshadowing in status {self.status.value}")
        return replace(self, status=AssetStatus.DEAD)
