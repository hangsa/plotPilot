import pytest
from application.storyos.services.sf_log_parser_service import SFLogParserService
from application.storyos.parsers.sf_log_regex_parser import SFLogRegexParser
from application.storyos.parsers.sf_log_format_validator import SFLogFormatValidator
from application.storyos.services.circuit_breaker_integration import (
    SFLogComplianceGate, ComplianceDecision,
)
from application.engine.services.circuit_breaker import CircuitBreaker
from domain.storyos.value_objects.format_error import FormatError
from domain.storyos.value_objects.predeclared import PredeclaredChanges, PredeclaredChange
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


def test_parse_returns_records():
    """spec §4.1 Step 5: Parser.parse(text, chapter_id) → list[SFLogRecord]"""
    svc = SFLogParserService(
        regex_parser=SFLogRegexParser(),
        format_validator=SFLogFormatValidator(),
    )
    text = 'A <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="blood" --> B'
    records = svc.parse(text, chapter_id=1)
    assert len(records) == 1
    assert records[0].log_type == SFLogType.MYSTERY_CLUE


def test_validate_format_returns_errors():
    """spec §4.1 Step 5: Parser.validate_format(records) → list[FormatError]"""
    svc = SFLogParserService(
        regex_parser=SFLogRegexParser(),
        format_validator=SFLogFormatValidator(),
    )
    records = [
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={"mystery_id": "m1"},  # 缺 content
            raw="<!-- ... -->", chapter_id=1, char_position=0, asset_id="m1",
        ),
    ]
    errors = svc.validate_format(records)
    assert len(errors) == 1
    assert errors[0].code == "MISSING_PARAM"


def test_match_against_predeclared_returns_match_report():
    """spec §4.1 Step 5: Parser.match_against_predeclared(records, predeclared) → MatchReport

    spec §4.4 锁定 MatchReport 字段：predeclared_total / predeclared_implemented /
    missing_changes / unexpected_records / match_rate + properties should_retry / has_warnings。
    """
    svc = SFLogParserService(
        regex_parser=SFLogRegexParser(),
        format_validator=SFLogFormatValidator(),
    )
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(log_type=SFLogType.MYSTERY_CLUE, asset_type="mystery", asset_id="m1"),
        PredeclaredChange(log_type=SFLogType.MYSTERY_CLUE, asset_type="mystery", asset_id="m2"),
    ])
    records = [
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE, params={"mystery_id": "m1", "content": "x"},
            raw="<!-- ... -->", chapter_id=1, char_position=0, asset_id="m1",
        ),
    ]
    report = svc.match_against_predeclared(records, predeclared)
    assert report.predeclared_total == 2
    assert report.predeclared_implemented == 1
    assert len(report.missing_changes) == 1
    assert report.match_rate == 0.5
    assert report.should_retry is True