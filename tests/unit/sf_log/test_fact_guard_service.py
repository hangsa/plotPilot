"""Unit tests for application/sf_log/fact_guard_service.py (Phase 2A §5 + Phase 2B Task 5).

Phase 2B refactor (Task 5): `cpms_invoker` was split into `sflog_invoker` +
`prose_invoker` + `parse_prose`. `evaluate()` now returns a 2-tuple
(GuardReport, rewritten_text_or_None) and requires `novel_id` + `chapter_id`
kwargs. These tests are migrated to the new API while preserving their
original behavioral intent.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.fact_guard_service import (
    FactGuardService,
    ProseRewriteResult,
    SFLogRewriteResult,
)
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


def _no_op_sflog_invoker(records, hits, attempt):
    return None  # CPMS unavailable


def _no_op_prose_invoker(text, records, hits, attempt):
    # Force rollback → loop ends at attempt 3 with force_pass.
    return ProseRewriteResult(
        new_chapter_text=text, new_records=records, rollback_signal=True,
    )


def _no_op_parse_prose(text, chapter_number):
    return []


def _build_svc(engine, sflog_invoker=None, prose_invoker=None, parse_prose=None):
    return FactGuardService(
        engine=engine,
        sflog_invoker=sflog_invoker or _no_op_sflog_invoker,
        prose_invoker=prose_invoker or _no_op_prose_invoker,
        parse_prose=parse_prose or _no_op_parse_prose,
    )


def test_first_pass_clean(clean_engine, bible):
    svc = _build_svc(clean_engine)
    report, rewritten = svc.evaluate(
        chapter_text="any text without the unique phrase",
        sflog_records=_records(),
        bible_snapshot=bible,
        novel_id="n", chapter_id=1,
    )
    assert rewritten is None
    assert report.passed is True
    assert report.attempt == 1
    assert report.forced_pass is False


def test_three_failures_force_pass(mock_engine, bible):
    """Both sflog attempts and prose attempt all hit HARD → forced_pass at attempt 3."""
    fail_invoker = MagicMock(return_value=None)  # sflog rewrite returns None → no fix
    svc = _build_svc(mock_engine, sflog_invoker=fail_invoker)
    report, rewritten = svc.evaluate(
        chapter_text="any text always_present_keyword here",
        sflog_records=_records(),
        bible_snapshot=bible,
        novel_id="n", chapter_id=1,
    )
    assert rewritten is None
    assert report.passed is True
    assert report.forced_pass is True
    assert report.attempt == 3
    assert len(report.hits) >= 1


def test_first_fail_second_pass_succeeds(mock_engine, bible):
    """sflog rewrite returns clean records on attempt 2 → attempt 2 passes."""
    def sflog_invoker(records, hits, attempt):
        # Replace with records that don't trigger the rule (different log_type
        # so the rule's applies_to filter skips them).
        return SFLogRewriteResult(
            records=[
                SFLogRecord(
                    log_type=SFLogType.CHARACTER_EMOTION,
                    params={"subject": "alice", "object": "y"},
                    raw='<!-- SF_LOG character_emotion subject="alice" object="y" -->',
                    chapter_id=1,
                    char_position=0,
                )
            ],
        )
    svc = _build_svc(mock_engine, sflog_invoker=sflog_invoker)
    report, rewritten = svc.evaluate(
        chapter_text="text always_present_keyword",
        sflog_records=_records(),
        bible_snapshot=bible,
        novel_id="n", chapter_id=1,
    )
    assert rewritten is None
    assert report.passed is True
    assert report.attempt == 2  # 2nd attempt cleaned → pass


def test_disabled_rule_does_not_hit(clean_engine, bible):
    """Engine with rule disabled (not in rules dict) → no hits."""
    svc = _build_svc(clean_engine)
    report, _ = svc.evaluate(
        chapter_text="anything",
        sflog_records=_records(),
        bible_snapshot=bible,
        novel_id="n", chapter_id=1,
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
    svc = _build_svc(engine)
    report, _ = svc.evaluate(
        chapter_text="text with any_phrase",
        sflog_records=_records(),
        bible_snapshot=bible,
        novel_id="n", chapter_id=1,
    )
    assert report.passed is True
    assert report.forced_pass is False
    assert any(h.severity is Severity.SOFT for h in report.hits)