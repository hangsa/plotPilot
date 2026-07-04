"""BridgeResult — 14 字段完整结果（spec §3.2 锁定）。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.cascade import CascadeStep


class BridgeResult(BaseModel):
    """单次 bridge 调用的结果聚合（spec §3.2 锁定）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bridge_id: str
    chapter_id: int = Field(ge=1)
    transaction_id: str | None  # spec 锁定：可为 None

    # Evolution action 统计
    evolution_actions_applied: int = 0
    evolution_actions_skipped: int = 0
    skipped_log_types: list[SFLogType] = Field(default_factory=list)  # spec 锁定：枚举列表

    # Registry 更新统计
    registry_updates_applied: int = 0

    # Cascade 统计
    cascade_steps_executed: int = 0
    cascade_steps_blocked: list[CascadeStep] = Field(default_factory=list)  # spec 锁定：对象列表

    # SFLog 事件记录
    sflog_events_recorded: int = 0

    # 状态
    success: bool = False
    warnings: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None
