"""Value objects for Phase 2B prose rewrite result types."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass
from typing import Optional

import pytest


class TestProseRewriteResult:
    def test_fields(self):
        from application.sf_log.fact_guard_service import ProseRewriteResult

        r = ProseRewriteResult(new_chapter_text="x", new_records=[])
        assert r.new_chapter_text == "x"
        assert r.new_records == []
        assert r.rollback_signal is False          # default

    def test_rollback_signal_explicit(self):
        from application.sf_log.fact_guard_service import ProseRewriteResult

        r = ProseRewriteResult(new_chapter_text="x", new_records=[], rollback_signal=True)
        assert r.rollback_signal is True

    def test_is_frozen(self):
        from application.sf_log.fact_guard_service import ProseRewriteResult

        r = ProseRewriteResult(new_chapter_text="x", new_records=[])
        with pytest.raises(FrozenInstanceError):
            r.new_chapter_text = "y"               # type: ignore[misc]


class TestSFLogRewriteResult:
    def test_records_only(self):
        from application.sf_log.fact_guard_service import SFLogRewriteResult

        r = SFLogRewriteResult(records=[])
        assert r.records == []
        assert r.mode == "sflog"

    def test_is_frozen(self):
        from application.sf_log.fact_guard_service import SFLogRewriteResult

        r = SFLogRewriteResult(records=[])
        with pytest.raises(FrozenInstanceError):
            r.records = []                          # type: ignore[misc]


class TestFactGuardLogRow:
    def test_default_fields(self):
        from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
            FactGuardLogRow,
        )

        r = FactGuardLogRow(
            chapter_id=1,
            chapter_number=1,
            novel_id="n1",
            attempt=1,
            mode="sflog",
            action="passed",
        )
        assert r.hard_before == 0
        assert r.hard_after == 0
        assert r.rule_id is None
        assert r.severity is None
        assert r.diff_excerpt is None
        assert r.notes is None

    def test_is_frozen(self):
        from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
            FactGuardLogRow,
        )

        r = FactGuardLogRow(
            chapter_id=1, chapter_number=1, novel_id="n1",
            attempt=1, mode="sflog", action="passed",
        )
        with pytest.raises(FrozenInstanceError):
            r.action = "passed"                     # type: ignore[misc]


class TestFactGuardLogPage:
    def test_defaults(self):
        from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
            FactGuardLogPage,
        )

        p = FactGuardLogPage()
        assert p.rows == []
        assert p.total == 0