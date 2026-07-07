"""Rule 6 — knowledge_gain.no_omniscience (Phase 2A §4 table).

HARD hit if record subject (knowledge grantor) is not in bible.scene_cast_ids.
"""
from __future__ import annotations

from application.sf_log.bible_snapshot import ChapterBibleContext
from domain.sf_log.guard_report import GuardHit, Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


def evaluate(record: SFLogRecord, bible: ChapterBibleContext) -> list[GuardHit]:
    subject = record.params.get("subject")
    if subject is None:
        return []  # missing param → no assertion
    if bible.is_in_scene(subject):
        return []  # grantor in scene → ok
    return [
        GuardHit(
            rule_id="knowledge_gain.no_omniscience",
            sflog_id=record.raw,
            severity=Severity.HARD,
            message=f"知识赋予方 '{subject}' 不在 scene.cast 中（{bible.chapter_id}）",
        )
    ]