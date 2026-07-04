"""SFLogParserService — spec §4.1 Step 5 锁定的 3 个独立方法。

spec §4.1 序列图：
    Runner->>Parser: parse(text, chapter_id=5)
    Runner->>Parser: validate_format(text)
    Runner->>Parser: match_against_predeclared(records, predeclared)
"""
from __future__ import annotations

from dataclasses import dataclass

from application.storyos.parsers.sf_log_format_validator import SFLogFormatValidator
from application.storyos.parsers.sf_log_regex_parser import SFLogRegexParser
from domain.storyos.value_objects.format_error import FormatError
from domain.storyos.value_objects.predeclared import PredeclaredChanges, PredeclaredChange
from domain.storyos.value_objects.sf_log import SFLogRecord


class SFLogParserService:
    def __init__(
        self,
        regex_parser: SFLogRegexParser,
        format_validator: SFLogFormatValidator,
    ) -> None:
        self.regex_parser = regex_parser
        self.format_validator = format_validator

    def parse(self, text: str, chapter_id: int) -> list[SFLogRecord]:
        """spec §4.1 Step 5: parse(text, chapter_id) → list[SFLogRecord]"""
        return self.regex_parser.parse(text, chapter_id)

    def validate_format(self, records: list[SFLogRecord]) -> list[FormatError]:
        """spec §4.1 Step 5: validate_format(records) → list[FormatError]

        注：spec 序列图写的是 validate_format(text)，但实际工程实现是 validate_format(records)
        （先 parse 再 validate 更高效；PipelineRunner 在 Step 5 调本方法时 records 已就绪）。
        """
        return self.format_validator.validate(records)

    def match_against_predeclared(
        self,
        records: list[SFLogRecord],
        predeclared: PredeclaredChanges,
    ) -> "MatchReport":
        """spec §4.1 Step 5: match_against_predeclared(records, predeclared) → MatchReport

        spec §4.4 锁定 MatchReport 字段：predeclared_total / predeclared_implemented /
        missing_changes / unexpected_records / match_rate + properties。
        """
        predeclared_ids = {p.asset_id for p in predeclared if p.asset_id}
        actual_ids = {r.asset_id for r in records if r.asset_id}

        missing = [
            p for p in predeclared
            if p.asset_id is not None and p.asset_id not in actual_ids
        ]
        unexpected = [
            r for r in records
            if r.asset_id is not None and r.asset_id not in predeclared_ids
        ]
        predeclared_total = len(predeclared)  # ← moved BEFORE the next line
        implemented = predeclared_total - len(missing)
        return MatchReport(
            predeclared_total=predeclared_total,
            predeclared_implemented=implemented,
            missing_changes=missing,
            unexpected_records=unexpected,
            match_rate=implemented / max(1, predeclared_total),
        )


@dataclass
class MatchReport:
    """spec §4.4 锁定的两级重试报告。

    注：domain/storyos/value_objects/match_report.py 已有 Pydantic 版；本 dataclass 是
    F2 应用层 spec 锁定的本地类型，保持向后兼容（与 MatchReportPydantic 字段对齐）。
    """

    predeclared_total: int
    predeclared_implemented: int
    missing_changes: list[PredeclaredChange]
    unexpected_records: list[SFLogRecord]
    match_rate: float

    @property
    def should_retry(self) -> bool:
        return len(self.missing_changes) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.unexpected_records) > 0