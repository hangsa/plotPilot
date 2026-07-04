"""StoryOSMetrics — 6 指标聚合（spec §5.2 锁定）。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StoryOSMetrics(BaseModel):
    """单次 bridge 调用的 6 维指标。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sflog_count: int = 0
    applied_count: int = 0
    skipped_count: int = 0
    cascade_executed: int = 0
    cascade_blocked: int = 0
    bridge_duration_ms: int = 0