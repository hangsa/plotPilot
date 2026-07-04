"""SFLog 端点 DTO 测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.sflog_schemas import (
    SFLogRawResponse,
    SFLogRecordDTO,
    SFLogReparseResponse,
    MatchReportDTO,
)
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord
from domain.storyos.value_objects.match_report import MatchReport
from domain.storyos.value_objects.predeclared import PredeclaredChange
from domain.storyos.value_objects.format_error import FormatError


def _make_record() -> SFLogRecord:
    return SFLogRecord(
        log_type=SFLogType.MYSTERY_CLUE,
        params={"asset_id": "m1", "clue": "dagger"},
        raw="[SF_LOG:MYSTERY_CLUE asset_id=m1 clue=dagger]",
        chapter_id=3,
        char_position=42,
        asset_id="m1",
    )


def test_sflog_record_dto_from_domain():
    dto = SFLogRecordDTO.from_domain(_make_record())
    assert dto.log_type == SFLogType.MYSTERY_CLUE
    assert dto.chapter_id == 3
    assert dto.char_position == 42
    assert dto.asset_id == "m1"
    assert dto.params == {"asset_id": "m1", "clue": "dagger"}


def test_sflog_raw_response_includes_records():
    resp = SFLogRawResponse(
        chapter_id=3,
        raw_text="body text",
        sf_log_count=1,
        records=[SFLogRecordDTO.from_domain(_make_record())],
    )
    assert resp.chapter_id == 3
    assert resp.sf_log_count == 1
    assert len(resp.records) == 1


def test_match_report_dto_from_domain():
    report = MatchReport(
        predeclared_total=4,
        predeclared_implemented=3,
        missing_changes=[
            PredeclaredChange(
                log_type=SFLogType.GOAL_MILESTONE,
                asset_type="goal",
                asset_id="g9",
            )
        ],
        unexpected_records=[_make_record()],
    )
    dto = MatchReportDTO.from_domain(report)
    assert dto.predeclared_total == 4
    assert dto.predeclared_implemented == 3
    assert dto.match_rate == pytest.approx(0.75)
    assert dto.should_retry is True
    assert dto.has_warnings is True
    assert len(dto.missing_changes) == 1
    assert len(dto.unexpected_records) == 1


def test_match_report_dto_zero_predeclared_default_rate():
    """零 predeclared → match_rate == 1.0（spec §4.4 锁定）。"""
    report = MatchReport()
    dto = MatchReportDTO.from_domain(report)
    assert dto.match_rate == 1.0
    assert dto.predeclared_total == 0


def test_sflog_reparse_response_includes_match_report():
    report = MatchReport(predeclared_total=2, predeclared_implemented=2)
    resp = SFLogReparseResponse(
        chapter_id=5,
        parsed_count=2,
        format_errors=[
            FormatError(
                code="BAD_SYNTAX",
                message="missing closing bracket",
                raw_text="[SF_LOG:MYSTERY_CLUE...",
                char_position=120,
            )
        ],
        match_report=MatchReportDTO.from_domain(report),
    )
    assert resp.chapter_id == 5
    assert resp.parsed_count == 2
    assert len(resp.format_errors) == 1
    assert resp.format_errors[0].code == "BAD_SYNTAX"
    assert resp.match_report.match_rate == 1.0


def test_sflog_reparse_response_rejects_negative_parsed_count():
    with pytest.raises(ValidationError):
        SFLogReparseResponse(
            chapter_id=5,
            parsed_count=-1,
        )
