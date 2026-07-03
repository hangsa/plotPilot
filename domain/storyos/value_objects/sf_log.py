"""SFLogRecord + SFLogParam（sub-spec §1 锁定）。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import SFLogType


class SFLogParam(BaseModel):
    """SF_LOG 单个参数（key=value 解析结果）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    value: str


class SFLogRecord(BaseModel):
    """从章节文本中提取的单条 SF_LOG 记录。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    log_type: SFLogType
    params: dict[str, str] = Field(min_length=1)
    raw: str = Field(min_length=1)
    chapter_id: int = Field(ge=1)
    char_position: int = Field(ge=0)
    asset_id: str | None = None

    def get_param(self, key: str, default: str | None = None) -> str | None:
        return self.params.get(key, default)

    def get_required_param(self, key: str) -> str:
        if key not in self.params:
            log_type_val = (
                self.log_type.value
                if isinstance(self.log_type, SFLogType)
                else str(self.log_type)
            )
            raise ValueError(
                f"SFLogRecord requires param '{key}' for log_type {log_type_val}"
            )
        return self.params[key]
