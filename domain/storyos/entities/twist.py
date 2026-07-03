"""Twist 实体（sub-spec §2 锁定 6 类 TwistType）。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.storyos.contracts import AssetStatus


class TwistType(str, Enum):
    """Twist 的语义分类（sub-spec §2 锁定 6 类）。"""

    IDENTITY_REVEAL = "identity_reveal"            # 身份揭露（卧底/双面人/真身）
    BETRAYAL = "betrayal"                          # 背叛（盟友反目）
    FORTUNE_REVERSAL = "fortune_reversal"          # 命运反转
    WORLD_RULE_REVEAL = "world_rule_reveal"        # 世界规则揭示
    SACRIFICE = "sacrifice"                        # 牺牲
    TRUTH_REVEALED = "truth_revealed"              # 真相揭示


@dataclass(frozen=True)
class Twist:
    """叙事反转实体。"""

    id: str
    novel_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    twist_type: TwistType
    reveal_trigger: str | None = None
    forbidden_concurrent_twists: tuple[str, ...] = ()

    def __post_init__(self):
        if self.created_chapter < 1:
            raise ValueError("created_chapter must be >= 1")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
