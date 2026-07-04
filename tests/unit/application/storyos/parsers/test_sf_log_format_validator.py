import pytest
from application.storyos.parsers.sf_log_format_validator import SFLogFormatValidator
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.format_error import FormatError
from domain.storyos.value_objects.sf_log import SFLogRecord


def _rec(log_type=SFLogType.MYSTERY_CLUE, params=None):
    return SFLogRecord(
        log_type=log_type,
        params=params or {"mystery_id": "m1", "content": "x"},
        raw='<!-- ... -->',
        chapter_id=1,
        char_position=0,
    )


def test_validator_accepts_valid_record():
    v = SFLogFormatValidator()
    rec = _rec()
    errors = v.validate([rec])
    assert errors == []


def test_validator_rejects_missing_required_param():
    v = SFLogFormatValidator()
    rec = _rec(params={"mystery_id": "m1"})  # 缺 content
    errors = v.validate([rec])
    assert len(errors) == 1
    assert errors[0].code == "MISSING_PARAM"
    assert "content" in errors[0].message


def test_validator_rejects_empty_param_value():
    v = SFLogFormatValidator()
    rec = _rec(params={"mystery_id": "", "content": "x"})
    errors = v.validate([rec])
    assert any(e.code == "EMPTY_PARAM" for e in errors)


def test_validator_checks_log_type_specific_params():
    """每类 SFLogType 必填参数不同。"""
    v = SFLogFormatValidator()
    rec = _rec(
        log_type=SFLogType.CONFLICT_ESCALATE,
        params={"conflict_id": "c1"},  # 缺 intensity
    )
    errors = v.validate([rec])
    assert any(e.code == "MISSING_PARAM" and "intensity" in e.message for e in errors)


def test_validator_returns_empty_for_no_records():
    v = SFLogFormatValidator()
    assert v.validate([]) == []