"""3-attempt loop semantics for FactGuardService — Phase 2B Task 5."""
from __future__ import annotations

from typing import List

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


# ── helpers ────────────────────────────────────────────────────────────
def _record(sflog_id: str, log_type: str = "character_emotion", char_position: int = 0) -> SFLogRecord:
    # Accept either enum NAME (CHARACTER_EMOTION) or enum VALUE (character_emotion).
    try:
        resolved = SFLogType(log_type)
    except ValueError:
        resolved = SFLogType[log_type]
    return SFLogRecord(
        log_type=resolved,
        params={"subject": "alice", "object": "x"},
        raw=sflog_id,
        chapter_id=1,
        char_position=char_position,
    )


def _hit(rule_id: str, severity: Severity) -> GuardHit:
    return GuardHit(
        rule_id=rule_id, sflog_id="x", severity=severity,
        message="m", matched_text="t",
    )


def _engine_with(rule_id: str, severity: Severity) -> RegexEngine:
    # Note: spec sketch uses `applies_to=None` as a wildcard so the rule fires
    # regardless of record.log_type. We supply a permissive regex
    # (`.+` matches any non-empty window) so the rule always hits — that's
    # what the tests need to drive the 3-attempt loop.
    rule = EngineRule(
        id=rule_id,
        applies_to=None,                            # type: ignore[arg-type]
        severity=severity,
        description="d",
        pattern=".+",
    )
    return RegexEngine(rules={rule_id: rule})


def _bible(chapter_id: int = 1) -> ChapterBibleContext:
    return ChapterBibleContext(
        chapter_id=chapter_id, scene_cast_ids=frozenset(),
        characters=(), worldbuilding_links={},
    )


# ── tests ──────────────────────────────────────────────────────────────
class TestSflogAttemptClearsHard:
    def test_full_pass_first_attempt_skips_prose(self):
        engine = _engine_with("r1", Severity.SOFT)
        svc = FactGuardService(
            engine=engine,
            sflog_invoker=lambda r, h, a: pytest.fail("sflog should NOT be called"),
            prose_invoker=lambda t, r, h, a: pytest.fail("prose should NOT be called"),
            parse_prose=lambda t, n: [],
        )
        report, rewritten = svc.evaluate(
            "chapter text", [_record("s1", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        assert report.passed is True
        assert report.forced_pass is False
        assert report.attempt == 1
        assert rewritten is None


class TestTwoSflogFailuresThenProse:
    def test_prose_attempt_after_two_sflog_failures(self):
        engine = _engine_with("r1", Severity.HARD)
        sflog_calls: list = []

        def sflog_invoker(records, hits, attempt):
            sflog_calls.append(attempt)
            return None                                        # CPMS unavailable

        prose_calls: list = []

        def prose_invoker(text, records, hits, attempt):
            prose_calls.append((text, list(records), list(hits), attempt))
            # Signal rollback → force_pass
            return ProseRewriteResult(
                new_chapter_text=text, new_records=records,
                rollback_signal=True,
            )

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=sflog_invoker,
            prose_invoker=prose_invoker,
            parse_prose=lambda t, n: [],
        )
        report, rewritten = svc.evaluate(
            "x", [_record("s", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        assert sflog_calls == [1, 2]
        assert len(prose_calls) == 1
        assert prose_calls[0][3] == 3
        assert report.passed is True
        assert report.forced_pass is True
        assert report.attempt == 3
        assert rewritten is None                                    # rolled back


class TestRegressionGuard:
    def test_prose_rewrite_rolled_back_on_regression(self):
        engine = _engine_with("r1", Severity.HARD)

        def prose_invoker(text, records, hits, attempt):
            return ProseRewriteResult(
                new_chapter_text="REWRITTEN", new_records=[],
                rollback_signal=False,
            )

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=lambda r, h, a: None,
            prose_invoker=prose_invoker,
            # parse_prose returns records that produce 1 HARD hit
            parse_prose=lambda t, n: [_record("s", "CHARACTER_EMOTION")],
        )
        report, rewritten = svc.evaluate(
            "ORIGINAL", [_record("s", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        assert rewritten is None                                   # rollback
        assert report.notes == "prose_rollback_regression"

    def test_prose_rewrite_kept_when_hard_count_does_not_increase(self):
        engine = _engine_with("r1", Severity.HARD)

        def prose_invoker(text, records, hits, attempt):
            return ProseRewriteResult(
                new_chapter_text="ALIGNED", new_records=[],
                rollback_signal=False,
            )

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=lambda r, h, a: None,
            prose_invoker=prose_invoker,
            parse_prose=lambda t, n: [],                            # 0 records → 0 HARD
        )
        report, rewritten = svc.evaluate(
            "ORIGINAL", [_record("s", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        assert rewritten == "ALIGNED"
        assert "prose_rewrite" in (report.notes or "")


class TestNullSafePaths:
    def test_sflog_invoker_returning_none_treated_as_no_rewrite(self):
        engine = _engine_with("r1", Severity.HARD)
        sflog_calls: list = []

        def sflog_invoker(records, hits, attempt):
            sflog_calls.append(attempt)
            return None

        def prose_invoker(text, records, hits, attempt):
            return ProseRewriteResult(
                new_chapter_text=text, new_records=records,
                rollback_signal=True,
            )

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=sflog_invoker,
            prose_invoker=prose_invoker,
            parse_prose=lambda t, n: [],
        )
        report, _ = svc.evaluate(
            "x", [_record("s", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        assert sflog_calls == [1, 2]


class TestExceptions:
    def test_prose_invoker_exception_propagates(self):
        """Phase 2B: prose exceptions DO propagate — they signal an infra failure
        and the pipeline hook (Task 8) is responsible for the outer try/except.
        """
        engine = _engine_with("r1", Severity.HARD)

        def prose_invoker(text, records, hits, attempt):
            raise RuntimeError("provider failed")

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=lambda r, h, a: None,
            prose_invoker=prose_invoker,
            parse_prose=lambda t, n: [],
        )
        with pytest.raises(RuntimeError, match="provider failed"):
            svc.evaluate(
                "x", [_record("s", "CHARACTER_EMOTION")],
                _bible(), novel_id="n", chapter_id=1,
            )


class TestAuditIntegration:
    def test_audit_repo_writes_for_every_attempt(self):
        """Verify _log() is called for passed / rewritten / no_rewrite /
        rolled_back paths."""
        engine = _engine_with("r1", Severity.HARD)
        writes: list = []

        class FakeRepo:
            def append(self, row):
                writes.append({
                    "action": row.action, "attempt": row.attempt,
                    "mode": row.mode, "hard_before": row.hard_before,
                    "hard_after": row.hard_after,
                })
                return -1

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=lambda r, h, a: None,
            prose_invoker=lambda t, r, h, a: ProseRewriteResult(
                new_chapter_text=t, new_records=r, rollback_signal=True,
            ),
            parse_prose=lambda t, n: [],
            audit_repo=FakeRepo(),                                  # type: ignore[arg-type]
        )
        svc.evaluate(
            "x", [_record("s", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        actions = [w["action"] for w in writes]
        assert "no_rewrite_sflog" in actions
        assert "forced_pass_rollback_llm" in actions


class TestDiffFormat:
    def test_diff_excerpt_format(self):
        from application.sf_log.fact_guard_service import _format_diff_excerpt

        before = "x" * 300
        after = "y" * 300
        excerpt = _format_diff_excerpt(before, after)
        assert "<<<>>>" in excerpt
        assert len(excerpt) <= 510
        parts = excerpt.split("<<<>>>", 1)
        assert len(parts[0]) <= 250
        assert len(parts[1]) <= 250