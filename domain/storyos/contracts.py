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