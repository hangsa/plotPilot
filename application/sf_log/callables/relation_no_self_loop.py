"""Rule 1 — character_relation.no_self_loop (Phase 2A §4)."""
from __future__ import annotations

from application.sf_log.bible_snapshot import ChapterBibleContext
from domain.sf_log.guard_report import GuardHit, Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


def evaluate(record: SFLogRecord, bible: ChapterBibleContext) -> list[GuardHit]:
    subject = record.params.get("subject")
    obj = record.params.get("object")
    if subject is None or obj is None:
        return []
    if subject == obj:
        return [
            GuardHit(
                rule_id="character_relation.no_self_loop",
                sflog_id=record.raw,
                severity=Severity.HARD,
                message="关系变更主体==客体 '{}'（自循环）".format(subject),
            )
        ]
    return []