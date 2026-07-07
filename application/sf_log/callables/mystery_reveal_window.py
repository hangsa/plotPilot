"""Rule 8 — mystery_clue.no_premature_reveal (Phase 2A §4 table, simplified).

HARD hit if mystery_id is malformed (not alnum + dash + underscore).
Phase 2A deferred reveal-window check (real 'expected_paid_chapter' field absent
in v1.2) to Phase 2B per spec §11.
"""
from __future__ import annotations

import re

from application.sf_log.bible_snapshot import ChapterBibleContext
from domain.sf_log.guard_report import GuardHit, Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


_VALID_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def evaluate(record: SFLogRecord, bible: ChapterBibleContext) -> list[GuardHit]:
    mystery_id = record.params.get("mystery_id")
    if mystery_id is None:
        return []  # no mystery_id → rule not applicable
    if _VALID_ID.match(mystery_id):
        return []
    return [
        GuardHit(
            rule_id="mystery_clue.no_premature_reveal",
            sflog_id=record.raw,
            severity=Severity.HARD,
            message=f"mystery_id '{mystery_id}' 格式非法（仅允许字母数字 + _ -）",
        )
    ]