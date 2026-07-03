"""MatchReport（spec §4.4 锁定两级重试）。

spec §4.4 锁定字段：
  - predeclared_total: int
  - predeclared_implemented: int
  - missing_changes: list[PredeclaredChange]
  - unexpected_records: list[SFLogRecord]
  - match_rate: float
  - properties: should_retry / has_warnings
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field

from domain.storyos.value_objects.predeclared import PredeclaredChange
from domain.storyos.value_objects.sf_log import SFLogRecord


class MatchReport(BaseModel):
    """预声明 vs 实际 SF_LOG 的匹配报告（spec §4.4 锁定）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    predeclared_total: int = 0
    predeclared_implemented: int = 0
    missing_changes: list[PredeclaredChange] = Field(default_factory=list)
    unexpected_records: list[SFLogRecord] = Field(default_factory=list)

    @computed_field
    @property
    def match_rate(self) -> float:
        """spec §4.4 锁定：predeclared_implemented / predeclared_total。"""
        if self.predeclared_total == 0:
            return 1.0  # 无 predeclared 定义为完全匹配
        return self.predeclared_implemented / self.predeclared_total

    @property
    def should_retry(self) -> bool:
        return len(self.missing_changes) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.unexpected_records) > 0