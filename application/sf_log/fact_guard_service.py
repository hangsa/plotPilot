"""FactGuardService — orchestrates 3 attempts + force-pass (Phase 2A §5 + 2B §3).

Phase 2B: 3-attempt loop with auto-escalation.
  - Attempt 1, 2 → SF_LOG-mode (sflog_invoker)
  - Attempt 3    → Prose-mode with regression guard (prose_invoker + re-eval)
  - Final        → force_pass if hard persists

Python 3.9 compat: `from __future__ import annotations` defers `Optional[list]` etc.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Literal, Optional, Tuple, TYPE_CHECKING

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.regex_engine import RegexEngine
from domain.sf_log.guard_report import GuardReport, GuardHit, Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


# Action enum (mirrors SQL CHECK constraint — see plan §5 / migration):
#   passed | rewritten_sflog | no_rewrite_sflog | rewritten_prose |
#   forced_pass_rollback_llm | rolled_back_regression |
#   provider_failed | node_missing
FactGuardAction = Literal[
    "passed",
    "rewritten_sflog",
    "no_rewrite_sflog",
    "rewritten_prose",
    "forced_pass_rollback_llm",
    "rolled_back_regression",
    "provider_failed",
    "node_missing",
]
FactGuardMode = Literal["sflog", "prose"]


# CPMS invoker signature; injected from pipeline hook (Task 8)
# Deprecated: replaced by SFLogRewriteFn + ProseRewriteFn in Phase 2B Task 5.
CPMSInvoker = Callable[[List[SFLogRecord], List[GuardHit], int], Optional[List[SFLogRecord]]]


@dataclass
class FactGuardService:
    """Phase 2B: 3-attempt loop with sflog × 2 + prose × 1 + regression guard.

    audit_repo: optional. When set, every iteration writes a row so writers
    can review the LLM's history in Phase 2C UI.
    """
    engine: RegexEngine
    sflog_invoker: "SFLogRewriteFn"
    prose_invoker: "ProseRewriteFn"
    parse_prose: "ParseFn"
    audit_repo: Optional["FactGuardAuditRepository"] = None

    def evaluate(
        self,
        chapter_text: str,
        sflog_records: List[SFLogRecord],
        bible_snapshot: ChapterBibleContext,
        *,
        novel_id: str,
        chapter_id: int,
    ) -> Tuple[GuardReport, Optional[str]]:
        """3-attempt loop. Returns (GuardReport, rewritten_chapter_text or None).

        chapter_id is the SQLite rowid; chapter_number is derived from
        bible_snapshot.chapter_id (kept locally to disambiguate the two).
        """
        original_chapter_text = chapter_text
        final_hits: List[GuardHit] = []
        current_records = sflog_records
        chapter_number = bible_snapshot.chapter_id

        # ── Attempts 1, 2: SF_LOG-mode ───────────────────────────────
        for attempt in (1, 2):
            hits = self.engine.evaluate_chapter(
                current_records, chapter_text, bible_snapshot,
            )
            final_hits = hits
            hard = [h for h in hits if h.severity is Severity.HARD]

            if not hard:
                self._log(
                    novel_id=novel_id, chapter_id=chapter_id,
                    chapter_number=chapter_number,
                    action="passed", mode="sflog", attempt=attempt,
                    hard_before=0, hard_after=0,
                )
                return GuardReport(
                    passed=True, forced_pass=False, attempt=attempt, hits=hits,
                ), None

            rewritten = self.sflog_invoker(current_records, hard, attempt)
            if rewritten is not None:
                self._log(
                    novel_id=novel_id, chapter_id=chapter_id,
                    chapter_number=chapter_number,
                    action="rewritten_sflog", mode="sflog", attempt=attempt,
                    hard_before=0, hard_after=len(hard),
                )
                current_records = rewritten.records
            else:
                self._log(
                    novel_id=novel_id, chapter_id=chapter_id,
                    chapter_number=chapter_number,
                    action="no_rewrite_sflog", mode="sflog", attempt=attempt,
                    hard_before=0, hard_after=len(hard),
                )
            # continue loop with possibly-updated records

        # ── Attempt 3: Prose-mode with regression guard ──────────────
        hard_before = [h for h in final_hits if h.severity is Severity.HARD]
        if not hard_before:
            return GuardReport(
                passed=True, forced_pass=False, attempt=2, hits=final_hits,
            ), None

        prose_result = self.prose_invoker(
            chapter_text, current_records, hard_before, 3,
        )

        if prose_result.rollback_signal:
            self._log(
                novel_id=novel_id, chapter_id=chapter_id,
                chapter_number=chapter_number,
                action="forced_pass_rollback_llm", mode="prose", attempt=3,
                hard_before=len(hard_before), hard_after=len(hard_before),
                notes="llm_signal_REQUIRES_PROSE_ROLLBACK",
            )
            return GuardReport(
                passed=True, forced_pass=True, attempt=3, hits=final_hits,
                notes="prose_rollback",
            ), None

        # Re-parse new text, re-evaluate
        new_records = self.parse_prose(
            prose_result.new_chapter_text, chapter_number,
        )
        new_hits = self.engine.evaluate_chapter(
            new_records, prose_result.new_chapter_text, bible_snapshot,
        )
        new_hard = [h for h in new_hits if h.severity is Severity.HARD]

        if len(new_hard) < len(hard_before):
            # Accept: keep rewrite (strictly fewer hard hits than before)
            diff_excerpt = _format_diff_excerpt(
                original_chapter_text, prose_result.new_chapter_text,
            )
            self._log(
                novel_id=novel_id, chapter_id=chapter_id,
                chapter_number=chapter_number,
                action="rewritten_prose", mode="prose", attempt=3,
                hard_before=len(hard_before), hard_after=len(new_hard),
                diff_excerpt=diff_excerpt,
            )
            return GuardReport(
                passed=True, forced_pass=True, attempt=3, hits=new_hits,
                notes=f"prose_rewrite hard={len(new_hard)}",
            ), prose_result.new_chapter_text

        # Regression: rollback to original
        self._log(
            novel_id=novel_id, chapter_id=chapter_id,
            chapter_number=chapter_number,
            action="rolled_back_regression", mode="prose", attempt=3,
            hard_before=len(hard_before), hard_after=len(new_hard),
            notes="prose_rewrite_increased_hard",
        )
        return GuardReport(
            passed=True, forced_pass=True, attempt=3, hits=final_hits,
            notes="prose_rollback_regression",
        ), None

    def _log(
        self,
        *,
        novel_id: str,
        chapter_id: int,
        chapter_number: int,
        action: str,
        mode: str,
        attempt: int,
        hard_before: int,
        hard_after: int,
        diff_excerpt: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        if self.audit_repo is None:
            return
        from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
            FactGuardLogRow,
        )
        self.audit_repo.append(
            FactGuardLogRow(
                chapter_id=chapter_id,
                chapter_number=chapter_number,
                novel_id=novel_id,
                attempt=attempt,
                mode=mode,                          # type: ignore[arg-type]
                action=action,                      # type: ignore[arg-type]
                hard_before=hard_before,
                hard_after=hard_after,
                diff_excerpt=diff_excerpt,
                notes=notes,
            )
        )


# ── Phase 2B: prose rewrite value objects + callable type aliases ──


@dataclass(frozen=True)
class SFLogRewriteResult:
    """Outcome of a `sf_log_invoker` call. Records are the rewritten
    SF_LOG comment block; chapter text is unchanged.
    """
    records: List[SFLogRecord]


@dataclass(frozen=True)
class ProseRewriteResult:
    """Outcome of a `prose_invoker` call. The `new_chapter_text` is the
    rewritten prose; `new_records` is parsed from that text. If
    `rollback_signal` is True the caller MUST discard the rewrite.
    """
    new_chapter_text: str
    new_records: List[SFLogRecord]
    rollback_signal: bool = False


SFLogRewriteFn = Callable[
    [List[SFLogRecord], List[GuardHit], int],
    Optional[SFLogRewriteResult],
]
ProseRewriteFn = Callable[
    [str, List[SFLogRecord], List[GuardHit], int],
    ProseRewriteResult,
]
ParseFn = Callable[[str, int], List[SFLogRecord]]   # (text, chapter_number) → records


# Lazy forward-reference resolution (TYPE_CHECKING only — runtime-inert)
if TYPE_CHECKING:
    from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
        FactGuardAuditRepository,
    )


def _format_diff_excerpt(before: str, after: str) -> str:
    """Slice each side to 250 chars; glue with '<<<>>>'. Total ≤ 503 chars.

    Simple prefix-based diff — sufficient for a 500-char audit excerpt.
    Production detail (Hamming-style midpoint search) deferred to Phase 2C.
    """
    b = before[:250]
    a = after[:250]
    return f"{b}<<<>>>{a}"