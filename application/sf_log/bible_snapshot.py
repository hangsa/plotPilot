"""ChapterBibleContext — read-only bible snapshot at chapter start (Phase 2A §2).

Frozen dataclass; consumed by python_callable rules. Constructed by Step 5 hook
from ctx.scene.cast + ctx.worldbuilding.links. Not persisted; lives for one chapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AbstractSet, Dict, Tuple


@dataclass(frozen=True)
class ChapterBibleContext:
    """只读快照：章节开始时角色 + 世界关系图。"""

    chapter_id: int
    scene_cast_ids: AbstractSet[str]
    characters: Tuple[Dict[str, Any], ...]
    worldbuilding_links: Dict[str, list] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Coerce plain set into frozenset so the frozen snapshot stays immutable
        # even when callers pass a mutable set literal.
        if not isinstance(self.scene_cast_ids, frozenset):
            object.__setattr__(self, "scene_cast_ids", frozenset(self.scene_cast_ids))

    def is_in_scene(self, character_id: str) -> bool:
        return character_id in self.scene_cast_ids