"""SQLite repository for storyos_fact_guard_logs — Phase 2B §5.

Writes route through `WriteDispatch.enqueue_execute_sql` per D1 (§8).
Reads use a direct sqlite3.Connection (WriteDispatch is write-only).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from application.sf_log.fact_guard_service import FactGuardAction, FactGuardMode


_INSERT_SQL = """
INSERT INTO storyos_fact_guard_logs
  (chapter_id, chapter_number, novel_id, attempt, mode,
   action, hard_before, hard_after,
   rule_id, severity, diff_excerpt, notes)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_SELECT_FOR_CHAPTER = """
SELECT id, chapter_id, chapter_number, novel_id, attempt, mode,
       action, hard_before, hard_after, rule_id, severity,
       diff_excerpt, notes, created_at
FROM storyos_fact_guard_logs
WHERE chapter_id = ?
ORDER BY created_at ASC, id ASC
LIMIT ? OFFSET 0
"""

_SELECT_FOR_NOVEL = """
SELECT id, chapter_id, chapter_number, novel_id, attempt, mode,
       action, hard_before, hard_after, rule_id, severity,
       diff_excerpt, notes, created_at
FROM storyos_fact_guard_logs
WHERE novel_id = ?
ORDER BY created_at DESC, id DESC
LIMIT ? OFFSET ?
"""

_COUNT_FOR_CHAPTER = "SELECT COUNT(*) FROM storyos_fact_guard_logs WHERE chapter_id = ?"
_COUNT_FOR_NOVEL = "SELECT COUNT(*) FROM storyos_fact_guard_logs WHERE novel_id = ?"


@dataclass(frozen=True)
class FactGuardLogRow:
    chapter_id: int
    chapter_number: int
    novel_id: str
    attempt: int
    mode: "FactGuardMode"
    action: "FactGuardAction"
    hard_before: int = 0
    hard_after: int = 0
    rule_id: Optional[str] = None
    severity: Optional[str] = None
    diff_excerpt: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class FactGuardLogPage:
    rows: List[dict] = field(default_factory=list)
    total: int = 0


class FactGuardAuditRepository:
    """Append-only writes (via WriteDispatch) + read queries (direct DB)."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def append(self, row: FactGuardLogRow) -> int:
        """Queue INSERT into WriteDispatch. Returns -1 (queued) or 0 (rejected).
        Audit failures must not crash the pipeline (CLAUDE.md + R5).
        """
        try:
            from infrastructure.persistence.database.write_dispatch import (
                enqueue_execute_sql,
            )
            ok = enqueue_execute_sql(
                _INSERT_SQL,
                (
                    row.chapter_id, row.chapter_number, row.novel_id,
                    row.attempt, row.mode, row.action,
                    row.hard_before, row.hard_after,
                    row.rule_id, row.severity, row.diff_excerpt, row.notes,
                ),
            )
            return -1 if ok else 0
        except Exception:                       # noqa: BLE001
            return 0

    def _insert_via_direct_db(self, row: FactGuardLogRow) -> int:
        """Test-only path: bypass WriteDispatch and insert synchronously.
        Production code MUST NOT use this; it's exposed only so unit tests
        can verify insert-row construction without spinning up the writer
        thread.
        """
        with self._connect() as conn:
            cur = conn.execute(
                _INSERT_SQL,
                (
                    row.chapter_id, row.chapter_number, row.novel_id,
                    row.attempt, row.mode, row.action,
                    row.hard_before, row.hard_after,
                    row.rule_id, row.severity, row.diff_excerpt, row.notes,
                ),
            )
            conn.commit()
            return cur.lastrowid or 0

    def list_for_chapter(
        self, chapter_id: int, *, limit: int = 50, offset: int = 0,
    ) -> FactGuardLogPage:
        return self._paginate(
            _SELECT_FOR_CHAPTER, _COUNT_FOR_CHAPTER,
            (chapter_id, limit), (chapter_id,),
        )

    def list_for_novel(
        self, novel_id: str, *, limit: int = 50, offset: int = 0,
    ) -> FactGuardLogPage:
        return self._paginate(
            _SELECT_FOR_NOVEL, _COUNT_FOR_NOVEL,
            (novel_id, limit, offset), (novel_id,),
        )

    def _paginate(
        self, select_sql: str, count_sql: str,
        select_params: tuple, count_params: tuple,
    ) -> FactGuardLogPage:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(select_sql, select_params)
            rows = [dict(r) for r in cur.fetchall()]
            cur2 = conn.execute(count_sql, count_params)
            (total,) = cur2.fetchone()
        return FactGuardLogPage(rows=rows, total=total)
