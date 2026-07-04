"""SFLog 端点专用 DTO。"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord
from domain.storyos.value_objects.match_report import MatchReport
from domain.storyos.value_objects.predeclared import PredeclaredChange
from domain.storyos.value_objects.format_error import FormatError


class SFLogRecordDTO(BaseModel):
    """SFLogRecord 的 API 表示。"""

    model_config = ConfigDict(from_attributes=True)

    log_type: SFLogType
    params: dict[str, str]
    raw: str
    chapter_id: int
    char_position: int
    asset_id: Optional[str] = None

    @classmethod
    def from_domain(cls, record: SFLogRecord) -> "SFLogRecordDTO":
        return cls(
            log_type=record.log_type,
            params=dict(record.params),
            raw=record.raw,
            chapter_id=record.chapter_id,
            char_position=record.char_position,
            asset_id=record.asset_id,
        )


class MatchReportDTO(BaseModel):
    """MatchReport 的 API 表示（含 spec §4.4 锁定的 computed properties）。"""

    model_config = ConfigDict(from_attributes=True)

    predeclared_total: int
    predeclared_implemented: int
    missing_changes: list[PredeclaredChange]
    unexpected_records: list[SFLogRecord]
    match_rate: float
    should_retry: bool
    has_warnings: bool

    @classmethod
    def from_domain(cls, report: MatchReport) -> "MatchReportDTO":
        return cls(
            predeclared_total=report.predeclared_total,
            predeclared_implemented=report.predeclared_implemented,
            missing_changes=list(report.missing_changes),
            unexpected_records=list(report.unexpected_records),
            match_rate=report.match_rate,
            should_retry=report.should_retry,
            has_warnings=report.has_warnings,
        )


class SFLogRawResponse(BaseModel):
    """GET /sflog/raw/{chapter_id} 响应。"""

    model_config = ConfigDict(extra="forbid")

    chapter_id: int = Field(ge=1)
    raw_text: str
    sf_log_count: int = Field(ge=0)
    records: list[SFLogRecordDTO]


class SFLogReparseResponse(BaseModel):
    """POST /sflog/reparse/{chapter_id} 响应。"""

    model_config = ConfigDict(extra="forbid")

    chapter_id: int = Field(ge=1)
    parsed_count: int = Field(ge=0)
    format_errors: list[FormatError] = Field(default_factory=list)
    match_report: MatchReportDTO
