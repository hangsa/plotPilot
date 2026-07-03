"""StoryOS bounded context 的契约层（枚举 + 协议 + 常量）。"""
from __future__ import annotations

from enum import Enum


class AssetStatus(str, Enum):
    """narrative asset 的生命周期状态（spec §3.2 锁定 12 态）。"""

    ACTIVE = "active"
    ACCUMULATING = "accumulating"
    PLANTED = "planted"
    DEVELOPING = "developing"
    HIDDEN = "hidden"
    READY_TO_FULFILL = "ready_to_fulfill"
    ESCALATED = "escalated"
    REVEALED = "revealed"
    FULFILLED = "fulfilled"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"
    DEAD = "dead"


class SFLogType(str, Enum):
    """章节文本中 SF_LOG 注释的语义分类（spec 附录 A 锁定 11 类）。"""

    CHARACTER_EMOTION = "character_emotion"
    CHARACTER_RELATION_CHANGE = "character_relation_change"
    CHARACTER_LOCATION_CHANGE = "character_location_change"
    CHARACTER_PHYSICAL_CHANGE = "character_physical_change"
    KNOWLEDGE_GAIN = "knowledge_gain"
    CONFLICT_ESCALATE = "conflict_escalate"
    MYSTERY_CLUE = "mystery_clue"
    TWIST_REVEAL = "twist_reveal"
    EXPECTATION_FULFILL = "expectation_fulfill"
    GOAL_MILESTONE = "goal_milestone"
    REGISTRY_CREATE = "registry_create"


RELATIONAL_LOG_TYPES = frozenset(
    {
        SFLogType.CHARACTER_RELATION_CHANGE,
    }
)


class CascadeTrigger(str, Enum):
    """级联触发的语义分类（spec §3.2 锁定 6 类）。"""

    MYSTERY_REVEALED = "mystery_revealed"
    TWIST_REVEALED = "twist_revealed"
    REVEAL_REVEALED = "reveal_revealed"
    PROMISE_FULFILLED = "promise_fulfilled"
    CONFLICT_RESOLVED = "conflict_resolved"
    CONFLICT_ESCALATED = "conflict_escalated"


FORBIDDEN_TRANSITIONS: frozenset[tuple[AssetStatus, AssetStatus]] = frozenset({
    (AssetStatus.RESOLVED, AssetStatus.ACTIVE),
    (AssetStatus.FULFILLED, AssetStatus.ACTIVE),
    (AssetStatus.REVEALED, AssetStatus.HIDDEN),
    (AssetStatus.DEAD, AssetStatus.ACTIVE),
    (AssetStatus.ABANDONED, AssetStatus.PLANTED),
    (AssetStatus.ABANDONED, AssetStatus.DEVELOPING),
    (AssetStatus.RESOLVED, AssetStatus.PLANTED),
    (AssetStatus.FULFILLED, AssetStatus.PLANTED),
})


def is_forbidden_transition(src: AssetStatus, dst: AssetStatus) -> bool:
    """检查 src→dst 是否在 FORBIDDEN_TRANSITIONS 中。

    Raises:
        TypeError: src 或 dst 不是 AssetStatus 实例。
    """
    if not isinstance(src, AssetStatus):
        raise TypeError(f"src must be AssetStatus, got {type(src).__name__}")
    if not isinstance(dst, AssetStatus):
        raise TypeError(f"dst must be AssetStatus, got {type(dst).__name__}")
    return (src, dst) in FORBIDDEN_TRANSITIONS