from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.predeclared import PredeclaredChange
from domain.storyos.value_objects.sf_log import SFLogRecord
from domain.storyos.value_objects.match_report import MatchReport


def _change(asset_id="m1", log_type=SFLogType.MYSTERY_CLUE):
    return PredeclaredChange(log_type=log_type, asset_type="mystery", asset_id=asset_id)


def _record(asset_id="m1", log_type=SFLogType.MYSTERY_CLUE):
    return SFLogRecord(
        log_type=log_type,
        params={"k": "v"},
        raw="<!-- ... -->",
        chapter_id=1,
        char_position=0,
        asset_id=asset_id,
    )


def test_match_report_empty_no_retry_no_warnings():
    r = MatchReport()
    assert r.should_retry is False
    assert r.has_warnings is False
    assert r.predeclared_total == 0
    assert r.predeclared_implemented == 0
    assert r.match_rate == 1.0  # 0/0 定义为完全匹配


def test_match_report_partial_match_calculates_rate():
    """spec §4.4 锁定：match_rate = predeclared_implemented / predeclared_total。"""
    r = MatchReport(
        predeclared_total=4, predeclared_implemented=3,
        missing_changes=[_change()], unexpected_records=[],
    )
    assert r.match_rate == 0.75
    assert r.should_retry is True


def test_match_report_retry_when_missing():
    r = MatchReport(missing_changes=[_change()])
    assert r.should_retry is True
    assert r.has_warnings is False


def test_match_report_warning_when_unexpected():
    r = MatchReport(unexpected_records=[_record()])
    assert r.has_warnings is True
    assert r.should_retry is False


def test_match_report_both_can_be_true():
    r = MatchReport(
        missing_changes=[_change()],
        unexpected_records=[_record()],
    )
    assert r.should_retry is True
    assert r.has_warnings is True