"""StoryOS sub-spec §1 SFLogRecord + SFLogParam value object 测试。"""
import pytest
from pydantic import ValidationError

from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogParam, SFLogRecord


def test_sf_log_param_constructs():
    p = SFLogParam(key="char_id", value="alice")
    assert p.key == "char_id"
    assert p.value == "alice"


def test_sf_log_param_forbids_extra():
    with pytest.raises(ValidationError):
        SFLogParam(key="k", value="v", extra="x")


def test_sf_log_param_is_frozen():
    p = SFLogParam(key="k", value="v")
    with pytest.raises(ValidationError):
        p.key = "kk"  # type: ignore[misc]


def test_sf_log_record_minimum_required():
    rec = SFLogRecord(
        log_type=SFLogType.MYSTERY_CLUE,
        params={"mystery_id": "m1", "content": "blood"},
        raw='<!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="blood" -->',
        chapter_id=3,
        char_position=120,
    )
    assert rec.log_type == SFLogType.MYSTERY_CLUE
    assert rec.params == {"mystery_id": "m1", "content": "blood"}
    assert rec.chapter_id == 3
    assert rec.char_position == 120
    assert rec.asset_id is None


def test_sf_log_record_with_asset_id():
    rec = SFLogRecord(
        log_type=SFLogType.MYSTERY_CLUE,
        params={"mystery_id": "m1"},
        raw="<!-- SF_LOG ... -->",
        chapter_id=1,
        char_position=0,
        asset_id="m1",
    )
    assert rec.asset_id == "m1"


def test_sf_log_record_forbids_extra():
    with pytest.raises(ValidationError):
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={"k": "v"},
            raw="<!-- ... -->",
            chapter_id=1,
            char_position=0,
            extra="nope",
        )


def test_sf_log_record_get_param_returns_value():
    rec = SFLogRecord(
        log_type=SFLogType.MYSTERY_CLUE,
        params={"mystery_id": "m1", "content": "x"},
        raw="<!-- ... -->",
        chapter_id=1,
        char_position=0,
    )
    assert rec.get_param("mystery_id") == "m1"
    assert rec.get_param("missing") is None
    assert rec.get_param("missing", default="d") == "d"


def test_sf_log_record_get_required_param_raises():
    rec = SFLogRecord(
        log_type=SFLogType.MYSTERY_CLUE,
        params={"k": "v"},
        raw="<!-- ... -->",
        chapter_id=1,
        char_position=0,
    )
    with pytest.raises(ValueError, match="requires param 'mystery_id'"):
        rec.get_required_param("mystery_id")


def test_sf_log_record_chapter_id_must_be_positive():
    with pytest.raises(ValidationError):
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={"k": "v"},
            raw="<!-- ... -->",
            chapter_id=0,
            char_position=0,
        )


def test_sf_log_record_char_position_must_be_non_negative():
    with pytest.raises(ValidationError):
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={"k": "v"},
            raw="<!-- ... -->",
            chapter_id=1,
            char_position=-1,
        )


def test_sf_log_record_params_must_be_non_empty():
    with pytest.raises(ValidationError):
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={},
            raw="<!-- ... -->",
            chapter_id=1,
            char_position=0,
        )
