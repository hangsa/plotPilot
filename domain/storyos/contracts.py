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