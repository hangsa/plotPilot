"""Unit tests for application/sf_log/fact_guard_service.py (Phase 2A §5)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.fact_guard_service import FactGuardService
from application.sf_log.regex_engine import EngineRule, RegexEngine
from domain.sf_log.guard_report import GuardHit, Severity
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


@pytest.fixture
def mock_engine():
    """Engine with one rule that always hits (for forcing retries)."""
    rule = EngineRule(
        id="test.always_hits",
        applies_to=SFLogType.KNOWLEDGE_GAIN,
        severity=Severity.HARD,
        description="always",
        pattern="always_present_keyword",
    )
    return RegexEngine(rules={"test.always_hits": rule})


@pytest.fixture
def clean_engine():
    """Engine with one rule that never hits."""
    rule = EngineRule(
        id="test.never_hits",
        applies_to=SFLogType.KNOWLEDGE_GAIN,
        severity=Severity.HARD,
        description="never",
        pattern="UNIQUE_PHRASE_THAT_NEVER_APPEARS_12345",
    )
    return RegexEngine(rules={"test.never_hits": rule})


@pytest.fixture
def bible():
    return ChapterBibleContext(
        chapter_id=1,
        scene_cast_ids=frozenset({"alice"}),
        characters=(),
        worldbuilding_links={},
    )


def _records() -> list[SFLogRecord]:
    return [
        SFLogRecord(
            log_type=SFLogType.KNOWLEDGE_GAIN,
            params={"subject": "alice", "object": "x"},
            raw='<!-- SF_LOG knowledge_gain subject="alice" object="x" -->',
            chapter_id=1,
            char_position=0,
        )
    ]


def test_first_pass_clean(clean_engine, bible):
    svc = FactGuardService(engine=clean_engine, cpms_invoker=lambda *a, **k: None)
    report = svc.evaluate(
        chapter_text="any text without the unique phrase",
        sflog_records=_records(),
        bible_snapshot=bible,
    )
    assert report.passed is True
    assert report.attempt == 1
    assert report.forced_pass is False


def test_three_failures_force_pass(mock_engine, bible):
    """3 attempts all hit HARD → forced_pass at attempt 3."""
    fail_invoker = MagicMock(return_value=None)  # CPMS rewrite returns None → no fix
    svc = FactGuardService(engine=mock_engine, cpms_invoker=fail_invoker)
    report = svc.evaluate(
        chapter_text="any text always_present_keyword here",
        sflog_records=_records(),
        bible_snapshot=bible,
    )
    assert report.passed is True
    assert report.forced_pass is True
    assert report.attempt == 3
    assert len(report.hits) >= 1


def test_first_fail_second_pass_succeeds(mock_engine, bible):
    """CPMS rewrite returns clean records on attempt 2 → attempt 2 passes."""
    def cpms_invoker(records, hits, attempt):
        # Replace with records that don't trigger the rule (different log_type
        # so the rule's applies_to filter skips them).
        return [
            SFLogRecord(
                log_type=SFLogType.CHARACTER_EMOTION,
                params={"subject": "alice", "object": "y"},
                raw='<!-- SF_LOG character_emotion subject="alice" object="y" -->',
                chapter_id=1,
                char_position=0,
            )
        ]
    svc = FactGuardService(engine=mock_engine, cpms_invoker=cpms_invoker)
    report = svc.evaluate(
        chapter_text="text always_present_keyword",
        sflog_records=_records(),
        bible_snapshot=bible,
    )
    assert report.passed is True
    assert report.attempt == 2  # 2nd attempt cleaned → pass


def test_disabled_rule_does_not_hit(clean_engine, bible):
    """Engine with rule disabled (not in rules dict) → no hits."""
    svc = FactGuardService(engine=clean_engine, cpms_invoker=lambda *a, **k: None)
    report = svc.evaluate(
        chapter_text="anything",
        sflog_records=_records(),
        bible_snapshot=bible,
    )
    assert all(h.rule_id != "disabled" for h in report.hits)


def test_soft_hits_dont_block_pass(mock_engine, bible):
    """SOFT hit → passed=True, no retry."""
    soft_rule = EngineRule(
        id="test.soft_hit",
        applies_to=SFLogType.KNOWLEDGE_GAIN,
        severity=Severity.SOFT,
        description="soft",
        pattern="any_phrase",
    )
    engine = RegexEngine(rules={"test.soft_hit": soft_rule})
    svc = FactGuardService(engine=engine, cpms_invoker=lambda *a, **k: None)
    report = svc.evaluate(
        chapter_text="text with any_phrase",
        sflog_records=_records(),
        bible_snapshot=bible,
    )
    assert report.passed is True
    assert report.forced_pass is False
    assert any(h.severity is Severity.SOFT for h in report.hits)