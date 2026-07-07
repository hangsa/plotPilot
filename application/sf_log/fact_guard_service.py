"""FactGuardService — orchestrates 3 attempts + force-pass (Phase 2A §5).

Inputs:
- engine: pre-loaded RegexEngine (Task 5)
- cpms_invoker: callable(records, hits, attempt) -> Optional[list[SFLogRecord]]
                returns rewritten records (None = rewrite unavailable, skip)

Retry invariant: prose body NEVER changes; only SF_LOG records get rewritten.

Phase 2B additions: ProseRewriteResult + SFLogRewriteResult value objects
and callable type aliases for sf_log / prose invokers and the SF_LOG parser.

Python 3.9 compat: `from __future__ import annotations` defers `Optional[list]` etc.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Literal, Optional

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.regex_engine import RegexEngine
from domain.sf_log.guard_report import GuardReport, GuardHit, Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


# CPMS invoker signature; injected from pipeline hook (Task 8)
# Deprecated: replaced by SFLogRewriteFn + ProseRewriteFn in Phase 2B Task 5.
CPMSInvoker = Callable[[List[SFLogRecord], List[GuardHit], int], Optional[List[SFLogRecord]]]


@dataclass
class FactGuardService:
    engine: RegexEngine
    cpms_invoker: CPMSInvoker

    def evaluate(
        self,
        chapter_text: str,
        sflog_records: List[SFLogRecord],
        bible_snapshot: ChapterBibleContext,
    ) -> GuardReport:
        """Up to 3 attempts; on attempt 3 with HARD hits → force_pass.

        Corrected loop semantics (Phase 2A §5 + bug-fix):
        - Attempt 1 & 2: HARD hits → call cpms_invoker.
          - If cpms_invoker returns new records → continue with rewritten records.
          - If cpms_invoker returns None (unavailable) → keep current_records,
            continue the loop (do NOT return early).
        - Attempt 3: if HARD hits remain → force_pass with attempt=3.
        """
        current_records = sflog_records
        hits: List[GuardHit] = []
        for attempt in (1, 2, 3):
            hits = self.engine.evaluate_chapter(
                current_records, chapter_text, bible_snapshot,
            )
            hard = [h for h in hits if h.severity is Severity.HARD]
            if not hard:
                return GuardReport(
                    passed=True, forced_pass=False, attempt=attempt, hits=hits,
                )
            if attempt < 3:
                rewritten = self.cpms_invoker(current_records, hard, attempt)
                if rewritten is not None:
                    current_records = rewritten
                # If CPMS returns None, keep same records and try again.
        # attempt 3 still has HARD hits
        return GuardReport(
            passed=True, forced_pass=True, attempt=3, hits=hits,
        )


# ── Phase 2B: prose rewrite value objects + callable type aliases ──

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