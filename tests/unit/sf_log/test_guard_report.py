"""Unit tests for domain/sf_log/guard_report.py (Phase 2A)."""
from __future__ import annotations

import pytest

from domain.sf_log.guard_report import GuardHit, GuardReport, Severity


class TestSeverity:
    def test_hard_and_soft_values_are_strings(self):
        assert Severity.HARD.value == "hard"
        assert Severity.SOFT.value == "soft"


class TestGuardHit:
    def test_construct_with_required_fields(self):
        hit = GuardHit(
            rule_id="character_relation.no_self_loop",
            sflog_id="sf-001",
            severity=Severity.HARD,
            message="subject cannot equal object",
        )
        assert hit.rule_id == "character_relation.no_self_loop"
        assert hit.severity is Severity.HARD
        assert hit.matched_text is None

    def test_is_frozen_rejects_mutation(self):
        hit = GuardHit(
            rule_id="x", sflog_id="y", severity=Severity.HARD, message="m",
        )
        with pytest.raises((AttributeError, Exception)):
            hit.message = "new"  # type: ignore[misc]


class TestGuardReport:
    def test_passed_with_no_hits(self):
        report = GuardReport(
            passed=True, forced_pass=False, attempt=1, hits=[],
        )
        assert report.passed is True
        assert report.forced_pass is False
        assert report.attempt == 1
        assert report.hits == []

    def test_failed_with_hard_hits(self):
        hit = GuardHit(
            rule_id="r1", sflog_id="s1", severity=Severity.HARD, message="bad",
        )
        report = GuardReport(
            passed=False, forced_pass=False, attempt=1, hits=[hit],
        )
        assert report.passed is False
        assert len(report.hits) == 1

    def test_forced_pass_at_attempt_3(self):
        hit = GuardHit(
            rule_id="r1", sflog_id="s1", severity=Severity.HARD, message="bad",
        )
        report = GuardReport(
            passed=True, forced_pass=True, attempt=3, hits=[hit],
        )
        assert report.passed is True
        assert report.forced_pass is True
        assert report.attempt == 3