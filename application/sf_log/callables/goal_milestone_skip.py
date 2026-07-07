"""Rule 11 — goal_milestone.no_skip (Phase 2A §4 table).

Phase 2A simplification: structural check only — a record lacking `goal_id`
cannot be checked for "consecutive milestone" (no identity for cross-record
state). HARD hit when the param is missing/empty. The full cross-chapter
gap check is deferred to Phase 2B.
"""
from __future__ import annotations

from application.sf_log.bible_snapshot import ChapterBibleContext
from domain.sf_log.guard_report import GuardHit, Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


def evaluate(record: SFLogRecord, bible: ChapterBibleContext) -> list[GuardHit]:
    goal_id = record.params.get("goal_id")
    if goal_id:
        return []  # well-formed goal_id → defer real cross-chapter check to 2B
    return [
        GuardHit(
            rule_id="goal_milestone.no_skip",
            sflog_id=record.raw,
            severity=Severity.HARD,
            message="GOAL_MILESTONE 缺少 goal_id，无法判断是否跨章跳跃",
        )
    ]