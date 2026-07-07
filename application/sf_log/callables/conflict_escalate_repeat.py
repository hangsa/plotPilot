"""Rule 7 — conflict_escalate.no_repeat (Phase 2A §4 table).

Phase 2A simplification: structural check only — a record lacking
`conflict_id` cannot be checked for repeat (no identity for cross-record
state). SOFT hit when the param is missing/empty. The full "same
conflict_id > 1 per chapter" check is deferred to Phase 2B.
"""
from __future__ import annotations

from application.sf_log.bible_snapshot import ChapterBibleContext
from domain.sf_log.guard_report import GuardHit, Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


def evaluate(record: SFLogRecord, bible: ChapterBibleContext) -> list[GuardHit]:
    conflict_id = record.params.get("conflict_id")
    if conflict_id:
        return []  # well-formed conflict_id → defer real repeat check to 2B
    return [
        GuardHit(
            rule_id="conflict_escalate.no_repeat",
            sflog_id=record.raw,
            severity=Severity.SOFT,
            message="CONFLICT_ESCALATE 缺少 conflict_id，无法判断是否重复升级",
        )
    ]