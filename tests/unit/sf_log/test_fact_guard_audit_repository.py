"""Tests for FactGuardAuditRepository.

Audit writes route through WriteDispatch (per D1 §8) — these tests verify
the repository's *read* path and the insert row construction. The
`enqueue_execute_sql` enqueue path is tested implicitly via
`tests/integration/sf_log/test_prose_rewrite_regression_e2e.py`.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
    FactGuardAuditRepository,
    FactGuardLogPage,
    FactGuardLogRow,
)


@pytest.fixture
def db_path(tmp_path) -> str:
    """Set up an in-memory SQLite DB with the migration applied."""
    db = tmp_path / "test.db"
    db_uri = str(db)
    with sqlite3.connect(db_uri) as conn:
        conn.executescript(
            """
            CREATE TABLE chapters (id INTEGER PRIMARY KEY AUTOINCREMENT);
            CREATE TABLE storyos_fact_guard_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chapter_id INTEGER NOT NULL,
                chapter_number INTEGER NOT NULL,
                novel_id TEXT NOT NULL,
                attempt INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 3),
                mode TEXT NOT NULL CHECK (mode IN ('sflog','prose')),
                action TEXT NOT NULL,
                hard_before INTEGER NOT NULL DEFAULT 0,
                hard_after INTEGER NOT NULL DEFAULT 0,
                rule_id TEXT,
                severity TEXT,
                diff_excerpt TEXT,
                notes TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE
            );
            CREATE INDEX idx_fact_guard_logs_chapter
                ON storyos_fact_guard_logs (chapter_id, attempt);
            """
        )
        conn.execute("INSERT INTO chapters (id) VALUES (42)")
        conn.commit()
    return db_uri


class TestRepositoryDirectInsert:
    """Tests bypass WriteDispatch by calling _insert_via_direct_db() with a
    real connection (for test isolation; production code always goes through
    WriteDispatch per D1).
    """

    def test_insert_one_row(self, db_path):
        repo = FactGuardAuditRepository(db_path)
        row = FactGuardLogRow(
            chapter_id=42, chapter_number=7, novel_id="alpha",
            attempt=1, mode="sflog", action="passed",
            hard_before=0, hard_after=0,
        )
        repo._insert_via_direct_db(row)
        with sqlite3.connect(db_path) as conn:
            cur = conn.execute(
                "SELECT COUNT(*), action, mode FROM storyos_fact_guard_logs"
            )
            count, action, mode = cur.fetchone()
            assert count == 1
            assert action == "passed"
            assert mode == "sflog"

    def test_list_for_chapter(self, db_path):
        repo = FactGuardAuditRepository(db_path)
        for i in (1, 2, 3):
            repo._insert_via_direct_db(
                FactGuardLogRow(
                    chapter_id=42, chapter_number=7, novel_id="alpha",
                    attempt=i, mode="sflog", action="passed",
                )
            )
        page = repo.list_for_chapter(42, limit=10)
        assert page.total == 3
        assert len(page.rows) == 3

    def test_list_for_novel(self, db_path):
        repo = FactGuardAuditRepository(db_path)
        repo._insert_via_direct_db(
            FactGuardLogRow(
                chapter_id=42, chapter_number=7, novel_id="alpha",
                attempt=1, mode="sflog", action="passed",
            )
        )
        page = repo.list_for_novel("alpha", limit=10, offset=0)
        assert page.total == 1


class TestProductionAppend:
    """`append()` returns -1/0 synchronously; actual SQL fires on the writer thread.
    These tests verify the synchronous return contract.
    """

    def test_append_returns_minus_one_or_zero(self, db_path):
        repo = FactGuardAuditRepository(db_path)
        row = FactGuardLogRow(
            chapter_id=42, chapter_number=7, novel_id="alpha",
            attempt=1, mode="sflog", action="passed",
        )
        result = repo.append(row)
        assert result in (-1, 0)

    def test_append_swallows_exceptions(self, db_path):
        repo = FactGuardAuditRepository(db_path)
        row = FactGuardLogRow(
            chapter_id=-1, chapter_number=7, novel_id="alpha",
            attempt=1, mode="sflog", action="passed",
        )
        result = repo.append(row)
        assert result in (-1, 0)
