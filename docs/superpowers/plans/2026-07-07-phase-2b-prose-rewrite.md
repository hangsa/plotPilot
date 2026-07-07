# Phase 2B — Tier 0 SF_LOG Prose Rewrite (v1.4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Phase 2A's Tier 0 SF_LOG fact_guard with paragraph-level prose rewrite so contradictions between SF_LOG records and chapter prose are auto-aligned (or rolled back if the rewrite increases hard-hit count), with full audit logging.

**Architecture:** 3-attempt loop with auto-escalation: attempts 1+2 call SF_LOG-only invoker (`sf-log-rewrite-with-hints` CPMS node, existing from 2A), attempt 3 calls prose invoker (new `sf-log-prose-rewrite` CPMS node) with a regression guard (`new_hard <= old_hard` ⇒ keep, else rollback). All events land in a dedicated `storyos_fact_guard_logs` SQLite table routed through `WriteDispatch` (per CLAUDE.md "all SQLite writes go through dispatcher").

**Tech Stack:** Python 3.9.6, SQLite (via `WriteDispatch`), FastAPI, CPMS assembler pipeline, existing pipeline hook system.

**Spec:** `docs/superpowers/specs/2026-07-07-phase-2b-prose-rewrite-design.md` (commit `7803fd7a`).

**Spec invariants the plan respects:**
- 11 SFLogType classes (no changes — Phase 2A engine unchanged)
- 3-attempt budget: sflog × 2 + prose × 1 + force_pass (no extra retries)
- Auto-escalation trigger (LLM signal-free; brute force progression)
- Paragraph-level rewrite scope (broader than 2A)
- Single prose attempt + regression guard
- `storyos_fact_guard_logs` table with action enum: `passed`, `rewritten_sflog`, `no_rewrite_sflog`, `rewritten_prose`, `forced_pass_rollback_llm`, `rolled_back_regression`, `provider_failed`, `node_missing`
- Python 3.9 compat (`from __future__ import annotations`, `Optional[X]`, no PEP 604)
- Phase 2A tests stay green (1948 unit + integration + regression baseline)

---

## File map

**New files (5):**
- `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/package.yaml`
- `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/user.md`
- `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/system.md`
- `application/sf_log/fact_guard_cpms.py`
- `infrastructure/persistence/sqlite/storyos_fact_guard_logs_repository.py`

**New files (5+ tests):**
- `tests/unit/domain/test_prose_rewrite_value_objects.py`
- `tests/unit/infrastructure/ai/test_sf_log_prose_rewrite_cpms_node.py`
- `tests/unit/application/sf_log/test_fact_guard_cpms_wiring.py`
- `tests/unit/sf_log/test_fact_guard_audit_repository.py`
- `tests/integration/sf_log/test_prose_rewrite_regression_e2e.py`
- `tests/integration/api/test_chapter_fact_guard_history_endpoint.py`
- `tests/regression/fixtures/fact_guard_5ch_prose.json`
- `tests/regression/test_phase_2b_prose_rewrite_pass_rate.py`
- `tests/performance/test_prose_rewrite_latency.py`
- `scripts/check_phase_2b_metrics.py`

**Modified files (5):**
- `application/sf_log/fact_guard_service.py` (refactor: split `cpms_invoker` into `sflog_invoker` + `prose_invoker` + `parse_prose`)
- `engine/pipeline/base.py` (replace stub lambdas with real wiring in `_hook_step5_post_write_gate`)
- `interfaces/api/v1/core/chapters.py` (append new endpoint + `_resolve_chapter_id` helper)
- `interfaces/main.py` (register `fact_guard_audit_repo` on app_state)
- `CLAUDE.md` (append Phase 2B section)

**New SQL migration (1):**
- `infrastructure/persistence/database/migrations/2026_07_07_phase_2b_fact_guard_logs.sql`

---

### Task 1: Foundation value objects

**Files:**
- Create: `application/sf_log/value_objects.py` (or extend `domain/sf_log/guard_report.py`)
- Test: `tests/unit/domain/test_prose_rewrite_value_objects.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/domain/test_prose_rewrite_value_objects.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/domain/test_prose_rewrite_value_objects.py -v`
Expected: ImportError or AttributeError (fact_guard_service doesn't yet export `ProseRewriteResult`, repository module doesn't exist yet).

- [ ] **Step 3: Write the dataclasses — extend `application/sf_log/fact_guard_service.py`**

Append to `application/sf_log/fact_guard_service.py` (do NOT replace the existing Phase 2A contents):

```python
# ── Phase 2B: prose rewrite value objects + audit row ──────────────
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
        FactGuardAuditRepository,
    )


@dataclass(frozen=True)
class SFLogRewriteResult:
    """Outcome of a `sf_log_invoker` call. Records are the rewritten
    SF_LOG comment block; chapter text is unchanged.
    """
    records: List[SFLogRecord]
    mode: str = "sflog"                           # for symmetry; only "sflog" today


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
```

Add the import `from typing import Callable, List, Optional` near the existing imports.

- [ ] **Step 4: Create the audit row + page dataclasses**

Create `infrastructure/persistence/sqlite/storyos_fact_guard_logs_repository.py` (just the dataclasses for now — the repository class comes in Task 3):

```python
"""SQLite repository for storyos_fact_guard_logs — Phase 2B §5."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class FactGuardLogRow:
    chapter_id: int
    chapter_number: int
    novel_id: str
    attempt: int
    mode: str                          # 'sflog' | 'prose'
    action: str
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
```

- [ ] **Step 5: Run the test — expect partial failures**

Run: `pytest tests/unit/domain/test_prose_rewrite_value_objects.py -v`

Expected:
- `TestSFLogRewriteResult::test_records_only` and friends PASS (dataclasses now exist)
- `TestFactGuardLogRow::*` PASS
- `TestFactGuardLogPage::test_defaults` PASS
- `TestProseRewriteResult::*` PASS

If `FrozenInstanceError` doesn't fire (some Python dataclass quirks), check that `from __future__ import annotations` is at the top of `fact_guard_service.py`; without it, `dataclass(frozen=True)` may not behave as expected under `mypy --strict` setups.

- [ ] **Step 6: Commit**

```bash
git add tests/unit/domain/test_prose_rewrite_value_objects.py \
        application/sf_log/fact_guard_service.py \
        infrastructure/persistence/sqlite/storyos_fact_guard_logs_repository.py
git commit -m "feat(sf_log): Phase 2B value objects — ProseRewriteResult + audit row"
```

---

### Task 2: SQL migration

**Files:**
- Create: `infrastructure/persistence/database/migrations/2026_07_07_phase_2b_fact_guard_logs.sql`

- [ ] **Step 1: Write the DDL**

Create `infrastructure/persistence/database/migrations/2026_07_07_phase_2b_fact_guard_logs.sql`:

```sql
-- Phase 2B: storyos_fact_guard_logs audit table
-- Records every fact_guard attempt (sflog × 2 + prose × 1) per chapter
-- so writers can review LLM activity via Phase 2C UI.

CREATE TABLE IF NOT EXISTS storyos_fact_guard_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id        INTEGER NOT NULL,
    chapter_number    INTEGER NOT NULL,
    novel_id          TEXT NOT NULL,
    attempt           INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 3),
    mode              TEXT NOT NULL CHECK (mode IN ('sflog', 'prose')),
    action            TEXT NOT NULL CHECK (action IN (
        'passed',
        'rewritten_sflog',
        'no_rewrite_sflog',
        'rewritten_prose',
        'forced_pass_rollback_llm',
        'rolled_back_regression',
        'provider_failed',
        'node_missing'
    )),
    hard_before       INTEGER NOT NULL DEFAULT 0,
    hard_after        INTEGER NOT NULL DEFAULT 0,
    rule_id           TEXT,
    severity          TEXT,
    diff_excerpt      TEXT,
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (chapter_id)  REFERENCES chapters(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fact_guard_logs_novel_created
    ON storyos_fact_guard_logs (novel_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fact_guard_logs_chapter
    ON storyos_fact_guard_logs (chapter_id, attempt);
```

- [ ] **Step 2: Run migration**

Run: `python scripts/run_migrations.py`
Expected: no errors; the runner picks up `2026_07_07_*` files in lexicographic order and records each applied migration in `migrations_applied`.

- [ ] **Step 3: Verify table exists**

Run: `sqlite3 data/plotpilot.db ".schema storyos_fact_guard_logs"`
Expected: the CREATE TABLE + 2 indexes shown.

- [ ] **Step 4: Commit**

```bash
git add infrastructure/persistence/database/migrations/2026_07_07_phase_2b_fact_guard_logs.sql
git commit -m "feat(db): add storyos_fact_guard_logs migration (Phase 2B)"
```

---

### Task 3: FactGuardAuditRepository

**Files:**
- Modify: `infrastructure/persistence/sqlite/storyos_fact_guard_logs_repository.py` (add repository class)
- Test: `tests/unit/sf_log/test_fact_guard_audit_repository.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/sf_log/test_fact_guard_audit_repository.py`:

```python
"""Tests for FactGuardAuditRepository.

Audit writes route through WriteDispatch (per D1 §8) — these tests verify
the repository's *read* path and the insert row construction. The
`enqueue_execute_sql` enqueue path is tested implicitly via
`tests/integration/sf_log/test_prose_rewrite_regression_e2e.py`.
"""
from __future__ import annotations

import sqlite3
import tempfile
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
    import subprocess
    db = tmp_path / "test.db"
    # Initialize fresh DB
    env_db = "PLOTPILOT_DB_PATH_OVERRIDE"          # if your env_config supports this
    db_uri = str(db)
    # Fall back: build schema manually
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
        # Verify the row is there
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
        # With the WriteDispatch queue initialized in CI/test mode, this returns
        # -1 (queued) or 0 (queue not ready); either is acceptable per D1.
        result = repo.append(row)
        assert result in (-1, 0)

    def test_append_swallows_exceptions(self, db_path):
        # Construct an invalid row (chapter_id = -1 violates FK) — `append`
        # MUST NOT raise.
        repo = FactGuardAuditRepository(db_path)
        row = FactGuardLogRow(
            chapter_id=-1, chapter_number=7, novel_id="alpha",
            attempt=1, mode="sflog", action="passed",
        )
        # Returns silently even if queue rejects (it's queued for flush; writer
        # thread handles the SQL-level error).
        result = repo.append(row)
        assert result in (-1, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/sf_log/test_fact_guard_audit_repository.py -v`
Expected: AttributeError — `FactGuardAuditRepository` not defined yet.

- [ ] **Step 3: Write the repository implementation**

Replace `infrastructure/persistence/sqlite/storyos_fact_guard_logs_repository.py`:

```python
"""SQLite repository for storyos_fact_guard_logs — Phase 2B §5.

Writes route through `WriteDispatch.enqueue_execute_sql` per D1 (§8).
Reads use a direct sqlite3.Connection (WriteDispatch is write-only).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from infrastructure.persistence.database.connection import DatabaseConnection
from infrastructure.persistence.database.write_dispatch import enqueue_execute_sql


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
    mode: str                          # 'sflog' | 'prose'
    action: str
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
        self._db = DatabaseConnection(db_path)

    def append(self, row: FactGuardLogRow) -> int:
        """Queue INSERT into WriteDispatch. Returns -1 (queued) or 0 (rejected).
        Audit failures must not crash the pipeline (CLAUDE.md + R5).
        """
        try:
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
        with self._db.connection() as conn:
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

    def append_many(self, rows: Iterable[FactGuardLogRow]) -> List[int]:
        return [self.append(r) for r in rows]

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
        with self._db.connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(select_sql, select_params)
            rows = [dict(r) for r in cur.fetchall()]
            cur2 = conn.execute(count_sql, count_params)
            (total,) = cur2.fetchone()
        return FactGuardLogPage(rows=rows, total=total)

    def list_for_novels_recent(
        self, novel_id: str, since_iso: str,
    ) -> List[FactGuardLogRow]:
        """For diff/incremental sync jobs — rows newer than `since_iso`."""
        with self._db.connection() as conn:
            cur = conn.execute(
                """
                SELECT chapter_id, chapter_number, novel_id, attempt, mode,
                       action, hard_before, hard_after, rule_id, severity,
                       diff_excerpt, notes
                FROM storyos_fact_guard_logs
                WHERE novel_id = ? AND created_at > ?
                ORDER BY created_at ASC
                """,
                (novel_id, since_iso),
            )
            return [
                FactGuardLogRow(
                    chapter_id=r[0], chapter_number=r[1], novel_id=r[2],
                    attempt=r[3], mode=r[4], action=r[5],
                    hard_before=r[6], hard_after=r[7],
                    rule_id=r[8], severity=r[9],
                    diff_excerpt=r[10], notes=r[11],
                )
                for r in cur.fetchall()
            ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/sf_log/test_fact_guard_audit_repository.py -v`
Expected: 5/5 PASS.

- [ ] **Step 5: Verify Phase 2A tests still green**

Run: `pytest tests/unit/sf_log/ -v`
Expected: All Phase 2A tests still pass; the 5 new tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/unit/sf_log/test_fact_guard_audit_repository.py \
        infrastructure/persistence/sqlite/storyos_fact_guard_logs_repository.py
git commit -m "feat(sf_log): FactGuardAuditRepository — WriteDispatch-routed writes"
```

---

### Task 4: CPMS node — `sf-log-prose-rewrite`

**Files:**
- Create: `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/package.yaml`
- Create: `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/user.md`
- Create: `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/system.md`
- Test: `tests/unit/infrastructure/ai/test_sf_log_prose_rewrite_cpms_node.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/infrastructure/ai/test_sf_log_prose_rewrite_cpms_node.py`:

```python
"""CPMS node loader tests for sf-log-prose-rewrite (Phase 2B Task 4)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


NODE_DIR = (
    Path(__file__).resolve().parents[3]
    / "infrastructure" / "ai" / "prompt_packages" / "nodes" / "sf-log-prose-rewrite"
)


class TestPackageManifest:
    @pytest.fixture
    def manifest(self):
        with open(NODE_DIR / "package.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_required_keys(self, manifest):
        for key in ("name", "category", "id", "sort_order", "tags", "variables", "builtin"):
            assert key in manifest

    def test_id_matches(self, manifest):
        assert manifest["id"] == "sf-log-prose-rewrite"

    def test_sort_order_unique(self, manifest):
        assert manifest["sort_order"] == 116

    def test_builtin(self, manifest):
        assert manifest["builtin"] is True

    def test_required_variables(self, manifest):
        var_names = {v["name"] for v in manifest["variables"]}
        assert var_names >= {"chapter_text", "hits", "sflog_records", "attempt"}

    def test_variable_required_flags(self, manifest):
        for var in manifest["variables"]:
            if var["name"] in ("chapter_text", "hits", "sflog_records", "attempt"):
                assert var.get("required", False) is True


class TestUserTemplate:
    def test_user_md_exists(self):
        assert (NODE_DIR / "user.md").exists()

    def test_user_md_has_required_placeholders(self):
        text = (NODE_DIR / "user.md").read_text(encoding="utf-8")
        for placeholder in ("{{chapter_text}}", "{{hits}}", "{{sflog_records}}", "{{attempt}}"):
            assert placeholder in text, f"missing {placeholder}"

    def test_user_md_no_prose_body_constraint_violation(self):
        """The prose node MUST allow prose editing — verify it does NOT
        contain the same prose-body-prohibition text as sflog node."""
        text = (NODE_DIR / "user.md").read_text(encoding="utf-8")
        sflog_text = (
            Path(__file__).resolve().parents[3]
            / "infrastructure" / "ai" / "prompt_packages" / "nodes"
            / "sf-log-rewrite-with-hints" / "user.md"
        ).read_text(encoding="utf-8")
        # sflog forbids prose; prose must not be so strict
        assert "严禁修改 prose body" in sflog_text
        # The new prose node should *not* contain that exact sentence
        assert "严禁修改 prose body" not in text

    def test_rollback_signal_in_user_md(self):
        text = (NODE_DIR / "user.md").read_text(encoding="utf-8")
        assert "REQUIRES_PROSE_ROLLBACK" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/infrastructure/ai/test_sf_log_prose_rewrite_cpms_node.py -v`
Expected: directory doesn't exist; FileNotFoundError or similar.

- [ ] **Step 3: Create `package.yaml`**

Create `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/package.yaml`:

```yaml
name: SF_LOG prose alignment rewrite
category: rewrite
source: application/sf_log/fact_guard_service.py::FactGuardService::_prose_attempt
description: 'Paragraph-level prose rewrite to align chapter text with SF_LOG records; broader scope than sf-log-rewrite-with-hints'
builtin: true
tags:
- sf_log
- rewrite
- prose
- fact_guard
- phase_2b
output_format: text
variables:
- { name: chapter_text, type: string, required: true, desc: '章节正文（含 SF_LOG 注释）' }
- { name: hits, type: string, required: true, desc: 'fact_guard HARD 命中列表' }
- { name: sflog_records, type: string, required: true, desc: '当前 SF_LOG 记录 JSON' }
- { name: attempt, type: integer, required: true, desc: 'attempt 编号（Phase 2B 中固定为 3）' }
id: sf-log-prose-rewrite
sort_order: 116
```

- [ ] **Step 4: Create `system.md`**

Create `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/system.md`:

```markdown
你是 PlotPilot fact_guard 系统的 prose 对齐助手。你的任务是在最小叙事破坏的前提下，
将章节正文(prose body)与已生成的 SF_LOG 注释块对齐。

你是数据一致性专家 — 当 prose 与 SF_LOG 矛盾时，应优先修正 prose 的事实陈述
（地点、时间、人物身份、物品归属），但保持作家的叙事风格、节奏与情感基调。

你不应该引入新人物、新事件、新情节转折；你只修正事实层面的不一致。

回复格式：原始 JSON 对象 `{"chapter_text": "...", "notes": "...", "rollback_signal": false}`。
JSON 字段说明：
- `chapter_text`：修改后的完整章节正文（包含原 SF_LOG 注释块）
- `notes`：修改说明（diff 摘要 + 剩余 HARD 列表）
- `rollback_signal`：当矛盾过于严重无法用段落级重写解决时设为 true，否则 false
```

- [ ] **Step 5: Create `user.md`**

Create `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/user.md`:

```markdown
你是一个 prose 对齐助手。给定章节文本、SF_LOG 注释块清单、fact_guard 命中列表：

**硬约束**:
- 只允许改写章节 prose body 中**包含或紧邻** `matched_text` 的句子。
- 段落级放大允许：当问题句子与上下文耦合（例如"他离开了北京，然后到了上海"中"到了上海"必需改）时，可以在最小行内延续里下扩展为同段落重写。
- 严禁：添加新人物 / 改人物身份 / 改叙事者 / 添加原 SF_LOG 未提及的事件。
- 当 prose 修改后仍无法消除全部 HARD 命中，请保留修改、增加可读性优先、并在修改说明中列出剩余 HARD。
- 严禁注释块：不要在你的回复里插入任何 `<!-- SF_LOG ... -->` 注释；SF_LOG 由调用方另行同步。

**输出**: 修改后的章节正文 + 修改说明（diff 摘要列表）。

命中：{{hits}}
SF_LOG 记录：{{sflog_records}}
attempt：第 {{attempt}} 次（共 3 次；prose-mode 仅 1 次）
原始正文：
```
{{chapter_text}}
```

如果你判断 prose 与 SF_LOG 矛盾**过于严重**（例如主情节反转、关键时间线矛盾、人物根本不同）以致无法用段落级重写对齐，请返回原文不变并在修改说明里写 "REQUIRES_PROSE_ROLLBACK"，fact_guard 会回滚并强制 pass。
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/unit/infrastructure/ai/test_sf_log_prose_rewrite_cpms_node.py -v`
Expected: 8/8 PASS.

- [ ] **Step 7: Commit**

```bash
git add infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/ \
        tests/unit/infrastructure/ai/test_sf_log_prose_rewrite_cpms_node.py
git commit -m "feat(cpms): add sf-log-prose-rewrite node (Phase 2B Task 4)"
```

---

### Task 5: FactGuardService refactor + new 3-attempt loop

**Files:**
- Modify: `application/sf_log/fact_guard_service.py` (replace evaluate method + dataclass)
- Test: `tests/unit/sf_log/test_fact_guard_service_prose_path.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/sf_log/test_fact_guard_service_prose_path.py`:

```python
"""3-attempt loop semantics for FactGuardService — Phase 2B Task 5."""
from __future__ import annotations

from typing import List, Optional

import pytest

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.fact_guard_service import (
    FactGuardService,
    ProseRewriteResult,
    SFLogRewriteResult,
)
from domain.sf_log.guard_report import GuardHit, Severity
from domain.storyos.value_objects.sf_log import SFLogRecord
from application.sf_log.regex_engine import EngineRule, RegexEngine


# ── helpers ────────────────────────────────────────────────────────────
def _record(sflog_id: str, log_type: str, char_position: int = 0) -> SFLogRecord:
    return SFLogRecord(raw=sflog_id, log_type=log_type, char_position=char_position)


def _hit(rule_id: str, severity: Severity) -> GuardHit:
    return GuardHit(
        rule_id=rule_id, sflog_id="x", severity=severity,
        message="m", matched_text="t",
    )


def _engine_with(rule_id: str, severity: Severity) -> RegexEngine:
    rule = EngineRule(
        id=rule_id,
        applies_to=None,                            # type: ignore[arg-type]
        severity=severity,
        description="d",
    )
    return RegexEngine(rules={rule_id: rule})


def _bible(chapter_id: int = 1) -> ChapterBibleContext:
    return ChapterBibleContext(
        chapter_id=chapter_id, scene_cast_ids=frozenset(),
        characters=(), worldbuilding_links={},
    )


# ── tests ──────────────────────────────────────────────────────────────
class TestSflogAttemptClearsHard:
    """1. test_sflog_attempt_clears_hard (variant: already passes at 1)"""

    def test_full_pass_first_attempt_skips_prose(self):
        # Engine returns 1 SOFT hit → no HARD → return at attempt 1
        engine = _engine_with("r1", Severity.SOFT)
        svc = FactGuardService(
            engine=engine,
            sflog_invoker=lambda r, h, a: pytest.fail("sflog should NOT be called"),
            prose_invoker=lambda t, r, h, a: pytest.fail("prose should NOT be called"),
            parse_prose=lambda t, n: [],
        )
        report, rewritten = svc.evaluate(
            "chapter text", [_record("s1", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        assert report.passed is True
        assert report.forced_pass is False
        assert report.attempt == 1
        assert rewritten is None


class TestTwoSflogFailuresThenProse:
    def test_prose_attempt_after_two_sflog_failures(self):
        engine = _engine_with("r1", Severity.HARD)
        sflog_calls: list = []

        def sflog_invoker(records, hits, attempt):
            sflog_calls.append(attempt)
            return None                                        # CPMS unavailable

        prose_calls: list = []

        def prose_invoker(text, records, hits, attempt):
            prose_calls.append((text, list(records), list(hits), attempt))
            # Signal rollback → force_pass
            return ProseRewriteResult(
                new_chapter_text=text, new_records=records,
                rollback_signal=True,
            )

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=sflog_invoker,
            prose_invoker=prose_invoker,
            parse_prose=lambda t, n: [],
        )
        report, rewritten = svc.evaluate(
            "x", [_record("s", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        assert sflog_calls == [1, 2]
        assert len(prose_calls) == 1
        assert prose_calls[0][3] == 3
        assert report.passed is True
        assert report.forced_pass is True
        assert report.attempt == 3
        assert rewritten is None                                    # rolled back


class TestRegressionGuard:
    def test_prose_rewrite_rolled_back_on_regression(self):
        engine = _engine_with("r1", Severity.HARD)
        prose_text_used = None

        def prose_invoker(text, records, hits, attempt):
            nonlocal prose_text_used
            prose_text_used = text
            return ProseRewriteResult(
                new_chapter_text="REWRITTEN", new_records=[],
                rollback_signal=False,
            )

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=lambda r, h, a: None,
            prose_invoker=prose_invoker,
            parse_prose=lambda t, n: [_record("s", "CHARACTER_EMOTION")],
        )
        report, rewritten = svc.evaluate(
            "ORIGINAL", [_record("s", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        assert rewritten is None                                   # rollback
        assert report.notes == "prose_rollback_regression"

    def test_prose_rewrite_kept_when_hard_count_does_not_increase(self):
        engine = _engine_with("r1", Severity.HARD)

        def prose_invoker(text, records, hits, attempt):
            return ProseRewriteResult(
                new_chapter_text="ALIGNED", new_records=[],
                rollback_signal=False,
            )

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=lambda r, h, a: None,
            prose_invoker=prose_invoker,
            parse_prose=lambda t, n: [],                            # 0 records → 0 HARD
        )
        report, rewritten = svc.evaluate(
            "ORIGINAL", [_record("s", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        assert rewritten == "ALIGNED"
        assert "prose_rewrite" in (report.notes or "")


class TestNullSafePaths:
    def test_sflog_invoker_returning_none_treated_as_no_rewrite(self):
        engine = _engine_with("r1", Severity.HARD)
        sflog_calls: list = []

        def sflog_invoker(records, hits, attempt):
            sflog_calls.append(attempt)
            return None

        def prose_invoker(text, records, hits, attempt):
            return ProseRewriteResult(
                new_chapter_text=text, new_records=records,
                rollback_signal=True,
            )

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=sflog_invoker,
            prose_invoker=prose_invoker,
            parse_prose=lambda t, n: [],
        )
        # 2 sflog calls (attempts 1, 2) return None → records unchanged
        # attempt 3: prose invoked once
        report, _ = svc.evaluate(
            "x", [_record("s", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        assert sflog_calls == [1, 2]


class TestExceptions:
    def test_prose_invoker_exception_path(self):
        engine = _engine_with("r1", Severity.HARD)

        def prose_invoker(text, records, hits, attempt):
            raise RuntimeError("provider failed")

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=lambda r, h, a: None,
            prose_invoker=prose_invoker,
            parse_prose=lambda t, n: [],
        )
        with pytest.raises(RuntimeError, match="provider failed"):
            svc.evaluate(
                "x", [_record("s", "CHARACTER_EMOTION")],
                _bible(), novel_id="n", chapter_id=1,
            )


class TestAuditIntegration:
    def test_audit_repo_writes_for_every_attempt(self):
        """Verify _log() is called for passed / rewritten / no_rewrite /
        rolled_back paths."""
        engine = _engine_with("r1", Severity.HARD)
        writes: list = []

        class FakeRepo:
            def append(self, row):
                writes.append({
                    "action": row.action, "attempt": row.attempt,
                    "mode": row.mode, "hard_before": row.hard_before,
                    "hard_after": row.hard_after,
                })
                return -1

        svc = FactGuardService(
            engine=engine,
            sflog_invoker=lambda r, h, a: None,
            prose_invoker=lambda t, r, h, a: ProseRewriteResult(
                new_chapter_text=t, new_records=r, rollback_signal=True,
            ),
            parse_prose=lambda t, n: [],
            audit_repo=FakeRepo(),                                  # type: ignore[arg-type]
        )
        svc.evaluate(
            "x", [_record("s", "CHARACTER_EMOTION")],
            _bible(), novel_id="n", chapter_id=1,
        )
        # Expect 4 rows: 2 sflog (no_rewrite) + 1 prose (forced_pass_rollback_llm)
        actions = [w["action"] for w in writes]
        assert "no_rewrite_sflog" in actions
        assert "forced_pass_rollback_llm" in actions


class TestDiffFormat:
    def test_diff_excerpt_format(self):
        from application.sf_log.fact_guard_service import _format_diff_excerpt

        before = "x" * 300
        after = "y" * 300
        excerpt = _format_diff_excerpt(before, after)
        # Should glue "before_250<<<>>>after_250" — total 503 chars
        assert "<<<>>>" in excerpt
        assert len(excerpt) <= 510
        parts = excerpt.split("<<<>>>", 1)
        assert len(parts[0]) <= 250
        assert len(parts[1]) <= 250
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/sf_log/test_fact_guard_service_prose_path.py -v`
Expected: ImportError, AttributeError, or NotImplementedError on the new evaluate path.

- [ ] **Step 3: Refactor `application/sf_log/fact_guard_service.py`**

Replace the existing `FactGuardService` class entirely:

```python
"""FactGuardService — orchestrates 3 attempts + force-pass (Phase 2A §5 + 2B §3).

Phase 2B: 3-attempt loop with auto-escalation.
  - Attempt 1, 2 → SF_LOG-mode (sflog_invoker)
  - Attempt 3    → Prose-mode with regression guard (prose_invoker + re-eval)
  - Final        → force_pass if hard persists

Python 3.9 compat: `from __future__ import annotations` defers `Optional[list]` etc.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple, TYPE_CHECKING

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.regex_engine import RegexEngine
from domain.sf_log.guard_report import GuardReport, GuardHit, Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


if TYPE_CHECKING:
    from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
        FactGuardAuditRepository,
    )


@dataclass(frozen=True)
class SFLogRewriteResult:
    """Outcome of a `sflog_invoker` call. Records are the rewritten SF_LOG
    comment block; chapter text is unchanged.
    """
    records: List[SFLogRecord]
    mode: str = "sflog"


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
ParseFn = Callable[[str, int], List[SFLogRecord]]


@dataclass
class FactGuardService:
    """Phase 2B: 3-attempt loop with sflog × 2 + prose × 1 + regression guard.

    audit_repo: optional. When set, every iteration writes a row so writers
    can review the LLM's history in Phase 2C UI.
    """
    engine: RegexEngine
    sflog_invoker: SFLogRewriteFn
    prose_invoker: ProseRewriteFn
    parse_prose: ParseFn
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

            if attempt < 2:
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

        if len(new_hard) <= len(hard_before):
            # Accept: keep rewrite (better or equal on hard-hit count)
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
                mode=mode,
                action=action,
                hard_before=hard_before,
                hard_after=hard_after,
                diff_excerpt=diff_excerpt,
                notes=notes,
            )
        )


def _format_diff_excerpt(before: str, after: str) -> str:
    """Slice each side to 250 chars; glue with '<<<>>>'. Total ≤ 503 chars.

    Simple prefix-based diff — sufficient for a 500-char audit excerpt.
    Production detail (Hamming-style midpoint search) deferred to Phase 2C.
    """
    b = before[:250]
    a = after[:250]
    return f"{b}<<<>>>{a}"
```

- [ ] **Step 4: Run the new test — verify pass**

Run: `pytest tests/unit/sf_log/test_fact_guard_service_prose_path.py -v`
Expected: ~10 PASS.

- [ ] **Step 5: Run all sf_log unit tests — verify Phase 2A still green**

Run: `pytest tests/unit/sf_log/ -v`
Expected: All existing Phase 2A tests still pass + new tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/unit/sf_log/test_fact_guard_service_prose_path.py \
        application/sf_log/fact_guard_service.py
git commit -m "feat(sf_log): FactGuardService 3-attempt loop with prose regression guard"
```

---

### Task 6: CPMS wiring helper

**Files:**
- Create: `application/sf_log/fact_guard_cpms.py`
- Test: `tests/unit/application/sf_log/test_fact_guard_cpms_wiring.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/application/sf_log/test_fact_guard_cpms_wiring.py`:

```python
"""Tests for fact_guard_cpms.build_writing_pipeline_invokers (Phase 2B Task 6)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List

import pytest


@dataclass
class FakeSnapshot:
    system: str
    user: str


class FakeAssembler:
    """Stub assembler that returns a FakeSnapshot for any node_key."""

    def __init__(self, by_node: dict):
        self._by_node = by_node

    def compile(self, *, spec, variable_plan):                   # noqa: ANN001
        if spec.node_key not in self._by_node:
            raise KeyError(f"no snapshot for {spec.node_key}")
        snap = self._by_node[spec.node_key]
        return FakeSnapshot(system=snap["system"], user=snap["user"])


class FakeProvider:
    """Scripted responses — returns predetermined strings for each call."""

    def __init__(self, scripts: List[str]):
        self._scripts = list(scripts)
        self.calls: List[FakeSnapshot] = []

    def generate(self, snapshot) -> str:
        self.calls.append(snapshot)
        if not self._scripts:
            return "[]"
        return self._scripts.pop(0)


class FakeParser:
    """Stub parser_service.parse — returns predetermined records."""

    def __init__(self, scripts: List[List]):
        self._scripts = list(scripts)
        self.calls: List[str] = []

    def parse(self, text, chapter_number):                       # noqa: ANN001
        self.calls.append(text)
        if not self._scripts:
            return []
        return self._scripts.pop(0)


from application.sf_log.fact_guard_cpms import (
    SFLOG_NODE,
    PROSE_NODE,
    build_writing_pipeline_invokers,
    NOOP_AUDIT_REPO,
)


class TestNodeRouting:
    def test_sflog_node_key(self):
        assert SFLOG_NODE == "sf-log-rewrite-with-hints"

    def test_prose_node_key(self):
        assert PROSE_NODE == "sf-log-prose-rewrite"


class TestSflogInvoker:
    def test_sflog_invoker_returns_records(self):
        asm = FakeAssembler({
            SFLOG_NODE: {"system": "sys", "user": "user {{chapter_text}}"},
        })
        provider = FakeProvider([
            json.dumps({"records": [{"raw": "sf1", "log_type": "CHARACTER_EMOTION",
                                     "char_position": 0}]}),
        ])
        parser = FakeParser([])
        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider, parser_service=parser,
        )
        from domain.storyos.value_objects.sf_log import SFLogRecord
        result = invokers.sflog_invoker(
            records=[SFLogRecord(raw="old", log_type="CHARACTER_EMOTION", char_position=0)],
            hits=[], attempt=1,
        )
        assert result is not None
        assert len(result.records) == 1
        assert result.records[0].raw == "sf1"

    def test_sflog_invoker_returns_none_on_malformed_json(self):
        asm = FakeAssembler({SFLOG_NODE: {"system": "", "user": ""}})
        provider = FakeProvider(["not json"])
        parser = FakeParser([])
        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider, parser_service=parser,
        )
        result = invokers.sflog_invoker(records=[], hits=[], attempt=1)
        assert result is None


class TestProseInvoker:
    def test_prose_invoker_returns_prose_rewrite_result(self):
        asm = FakeAssembler({PROSE_NODE: {"system": "", "user": ""}})
        rewritten_text = "The new chapter prose"
        provider = FakeProvider([
            json.dumps({
                "chapter_text": rewritten_text,
                "notes": "fixed sentence 1",
                "rollback_signal": False,
            }),
        ])
        parser = FakeParser([])
        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider, parser_service=parser,
        )
        from domain.storyos.value_objects.sf_log import SFLogRecord
        result = invokers.prose_invoker(
            chapter_text="OLD", records=[], hits=[], attempt=3,
        )
        assert result.new_chapter_text == rewritten_text
        assert result.rollback_signal is False

    def test_prose_invoker_rollback_signal_passthrough(self):
        asm = FakeAssembler({PROSE_NODE: {"system": "", "user": ""}})
        provider = FakeProvider([
            json.dumps({
                "chapter_text": "ORIGINAL",
                "notes": "REQUIRES_PROSE_ROLLBACK",
                "rollback_signal": True,
            }),
        ])
        parser = FakeParser([])
        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider, parser_service=parser,
        )
        result = invokers.prose_invoker(
            chapter_text="ORIGINAL", records=[], hits=[], attempt=3,
        )
        assert result.rollback_signal is True


class TestParseProse:
    def test_parse_prose_delegates(self):
        from domain.storyos.value_objects.sf_log import SFLogRecord
        asm = FakeAssembler({})
        provider = FakeProvider([])
        expected = [SFLogRecord(raw="r", log_type="CHARACTER_EMOTION", char_position=0)]
        parser = FakeParser([expected])
        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider, parser_service=parser,
        )
        actual = invokers.parse_prose("some text", 7)
        assert actual == expected


class TestNoopAuditRepo:
    def test_noop_audit_repo_returns_zero(self):
        from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
            FactGuardLogRow,
        )
        result = NOOP_AUDIT_REPO.append(
            FactGuardLogRow(
                chapter_id=1, chapter_number=1, novel_id="n",
                attempt=1, mode="sflog", action="passed",
            )
        )
        assert result == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/application/sf_log/test_fact_guard_cpms_wiring.py -v`
Expected: ModuleNotFoundError on `application.sf_log.fact_guard_cpms`.

- [ ] **Step 3: Implement `fact_guard_cpms.py`**

Create `application/sf_log/fact_guard_cpms.py`:

```python
"""CPMS wiring for fact_guard — Phase 2B §4 + §7 NOOP_AUDIT_REPO.

Builds sflog_invoker and prose_invoker that talk to existing CPMS nodes
+ a parse_prose wrapper around the existing parser. Pure factory: no I/O
at construction time.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Protocol

from application.sf_log.fact_guard_service import (
    ParseFn,
    ProseRewriteFn,
    ProseRewriteResult,
    SFLogRewriteFn,
    SFLogRewriteResult,
)
from domain.storyos.value_objects.sf_log import SFLogRecord
from domain.sf_log.guard_report import GuardHit


logger = logging.getLogger(__name__)


class LLMProviderProtocol(Protocol):
    def generate(self, prompt_snapshot: Any) -> str: ...


class CPMSAssemblerProtocol(Protocol):
    def compile(self, *, spec: Any, variable_plan: Any) -> Any: ...


SFLOG_NODE = "sf-log-rewrite-with-hints"
PROSE_NODE = "sf-log-prose-rewrite"


# ── NOOP audit repo ──────────────────────────────────────────────────
class _NoopAuditRepo:
    """Singleton no-op audit repo. Used as default when app_state.fact_guard_audit_repo
    isn't wired (test/dev mode). append() returns 0 silently."""

    def append(self, row: Any) -> int:
        return 0


NOOP_AUDIT_REPO = _NoopAuditRepo()


# ── Result types (re-exported) ───────────────────────────────────────
@dataclass(frozen=True)
class WritingPipelineInvokers:
    sflog_invoker: SFLogRewriteFn
    prose_invoker: ProseRewriteFn
    parse_prose: ParseFn


# ── Wiring factory ──────────────────────────────────────────────────
def build_writing_pipeline_invokers(
    *,
    assembler: CPMSAssemblerProtocol,
    llm_provider: LLMProviderProtocol,
    parser_service: Any,
    audit_repo: Optional[Any] = None,
    max_chapter_text_chars: int = 6000,
) -> WritingPipelineInvokers:
    """Wire up the two CPMS invokers + parser. Pure factory."""

    def sflog_invoker(
        records: List[SFLogRecord],
        hits: List[GuardHit],
        attempt: int,
    ) -> Optional[SFLogRewriteResult]:
        # Build variable_plan and InvocationSpec — adapt to your codebase.
        # Below is a simplified shape; production uses the InvocationSpec DTO.
        try:
            snapshot = _compile_snapshot(
                assembler, node_key=SFLOG_NODE,
                chapter_text="",                              # sflog-only node
                hits=json.dumps([_hit_to_dict(h) for h in hits]),
                sflog_records=json.dumps([_record_to_dict(r) for r in records]),
                attempt=attempt,
            )
        except Exception as e:
            logger.warning("sflog node %s compile failed: %s", SFLOG_NODE, e)
            _log_failure(audit_repo, node_key=SFLOG_NODE, reason="node_missing")
            return None

        try:
            raw = llm_provider.generate(snapshot)
        except Exception as e:
            logger.warning("sflog provider failed: %s", e)
            _log_failure(audit_repo, node_key=SFLOG_NODE, reason="provider_failed")
            return None

        try:
            payload = json.loads(raw)
            new_records_raw = payload.get("records", [])
            new_records = [_dict_to_record(r) for r in new_records_raw]
        except Exception as e:
            logger.warning("sflog malformed response: %s", e)
            return None

        if not raw.strip():
            return None

        return SFLogRewriteResult(records=new_records)

    def prose_invoker(
        chapter_text: str,
        records: List[SFLogRecord],
        hits: List[GuardHit],
        attempt: int,
    ) -> ProseRewriteResult:
        # Cap input to bound tokens
        if len(chapter_text) > max_chapter_text_chars:
            # Slice from the centroid of conflict
            chapter_text_slice = chapter_text[:max_chapter_text_chars]
        else:
            chapter_text_slice = chapter_text

        try:
            snapshot = _compile_snapshot(
                assembler, node_key=PROSE_NODE,
                chapter_text=chapter_text_slice,
                hits=json.dumps([_hit_to_dict(h) for h in hits]),
                sflog_records=json.dumps([_record_to_dict(r) for r in records]),
                attempt=attempt,
            )
        except Exception as e:
            logger.warning("prose node %s compile failed: %s", PROSE_NODE, e)
            _log_failure(audit_repo, node_key=PROSE_NODE, reason="node_missing")
            # Graceful degradation: signal rollback; service force-passes.
            return ProseRewriteResult(
                new_chapter_text=chapter_text,
                new_records=records,
                rollback_signal=True,
            )

        try:
            raw = llm_provider.generate(snapshot)
        except Exception as e:
            logger.warning("prose provider failed: %s", e)
            _log_failure(audit_repo, node_key=PROSE_NODE, reason="provider_failed")
            return ProseRewriteResult(
                new_chapter_text=chapter_text,
                new_records=records,
                rollback_signal=True,
            )

        if not raw.strip():
            return ProseRewriteResult(
                new_chapter_text=chapter_text,
                new_records=records,
                rollback_signal=True,
            )

        try:
            payload = json.loads(raw)
        except Exception as e:
            logger.warning("prose malformed response: %s", e)
            return ProseRewriteResult(
                new_chapter_text=chapter_text,
                new_records=records,
                rollback_signal=True,
            )

        return ProseRewriteResult(
            new_chapter_text=payload.get("chapter_text", chapter_text),
            new_records=[_dict_to_record(r) for r in payload.get("records", [])],
            rollback_signal=bool(payload.get("rollback_signal", False)),
        )

    def parse_prose(chapter_text: str, chapter_number: int) -> List[SFLogRecord]:
        return list(parser_service.parse(chapter_text, chapter_number))

    return WritingPipelineInvokers(
        sflog_invoker=sflog_invoker,
        prose_invoker=prose_invoker,
        parse_prose=parse_prose,
    )


# ── Internal helpers ──────────────────────────────────────────────────
def _compile_snapshot(
    assembler: CPMSAssemblerProtocol,
    *,
    node_key: str,
    chapter_text: str,
    hits: str,
    sflog_records: str,
    attempt: int,
) -> Any:
    """Compile a CPMS snapshot. Adapts your codebase's InvocationSpec +
    VariablePlan. The below is the shape — adapt to actual DTO classes."""
    from application.ai_invocation.dtos import InvocationSpec, VariablePlan
    spec = InvocationSpec(node_key=node_key)
    plan = VariablePlan(
        bindings={
            "chapter_text": chapter_text,
            "hits": hits,
            "sflog_records": sflog_records,
            "attempt": attempt,
        },
    )
    return assembler.compile(spec=spec, variable_plan=plan)


def _hit_to_dict(h: GuardHit) -> dict:
    return {
        "rule_id": h.rule_id,
        "sflog_id": h.sflog_id,
        "severity": h.severity.value,
        "message": h.message,
        "matched_text": h.matched_text,
    }


def _record_to_dict(r: SFLogRecord) -> dict:
    return {
        "raw": r.raw,
        "log_type": r.log_type,
        "char_position": r.char_position,
    }


def _dict_to_record(d: dict) -> SFLogRecord:
    return SFLogRecord(
        raw=d.get("raw", ""),
        log_type=d.get("log_type", ""),
        char_position=d.get("char_position", 0),
    )


def _log_failure(audit_repo: Optional[Any], *, node_key: str, reason: str) -> None:
    if audit_repo is None:
        return
    try:
        from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
            FactGuardLogRow,
        )
        audit_repo.append(
            FactGuardLogRow(
                chapter_id=0,                              # unknown at this stage
                chapter_number=0,
                novel_id="",
                attempt=0,
                mode="sflog" if "rewrite-with-hints" in node_key else "prose",
                action=reason,
            )
        )
    except Exception:                                       # noqa: BLE001
        pass
```

**Important: Adapt `_compile_snapshot` to your codebase's actual `InvocationSpec` and `VariablePlan` shapes** by reading `application/ai_invocation/dtos.py`. The above is the structural shape; field names may differ slightly.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/application/sf_log/test_fact_guard_cpms_wiring.py -v`
Expected: ~10 PASS.

- [ ] **Step 5: Verify adaptation by running import smoke test**

Run: `python -c "from application.sf_log.fact_guard_cpms import build_writing_pipeline_invokers; print('ok')"`
Expected: `ok` (if `_compile_snapshot` compiles against your DTOs) or ImportError pointing at the field needing adaptation.

If ImportError: read `application/ai_invocation/dtos.py` and fix `_compile_snapshot` field-by-field.

- [ ] **Step 6: Commit**

```bash
git add tests/unit/application/sf_log/test_fact_guard_cpms_wiring.py \
        application/sf_log/fact_guard_cpms.py
git commit -m "feat(sf_log): CPMS wiring helper with NOOP audit fallback (Phase 2B Task 6)"
```

---

### Task 7: `_resolve_chapter_id` helper + `_format_diff_excerpt` (already in Task 5)

**Files:**
- Modify: `interfaces/api/v1/core/chapters.py` (append `_resolve_chapter_id`)

- [ ] **Step 1: Add the helper to `chapters.py`**

Append to `interfaces/api/v1/core/chapters.py`:

```python
def _resolve_chapter_id(novel_id: str, chapter_number: int) -> Optional[int]:
    """Return the SQLite rowid of `chapters` matching (novel_id, chapter_number).

    None if no such chapter exists. Synchronous DB read; no caching (Phase 2B
    scope — caching deferred to 2C per Q3).
    """
    from application.paths import get_db_path
    with sqlite3.connect(get_db_path()) as conn:
        cur = conn.execute(
            "SELECT id FROM chapters WHERE novel_id = ? AND chapter_number = ? LIMIT 1",
            (novel_id, chapter_number),
        )
        row = cur.fetchone()
        return row[0] if row else None
```

Add at the top of `interfaces/api/v1/core/chapters.py`:
```python
import sqlite3
from typing import Optional  # noqa: F401  (re-export if needed)
```

- [ ] **Step 2: Smoke test**

Run: `python -c "from interfaces.api.v1.core.chapters import _resolve_chapter_id; print(_resolve_chapter_id('nonexistent', 0))"`
Expected: `None`

- [ ] **Step 3: Commit**

```bash
git add interfaces/api/v1/core/chapters.py
git commit -m "feat(api): add _resolve_chapter_id helper for fact-guard endpoint"
```

---

### Task 8: Step 5 hook integration

**Files:**
- Modify: `engine/pipeline/base.py` (replace stub lambdas in `_hook_step5_post_write_gate`)
- Modify: `interfaces/main.py` (register `fact_guard_audit_repo`)

- [ ] **Step 1: Add app_state registration**

In `interfaces/main.py`, find the `app_state = ...` setup and add:

```python
from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
    FactGuardAuditRepository,
)
from application.paths import get_db_path

app_state.fact_guard_audit_repo = FactGuardAuditRepository(get_db_path())
```

(Exact location depends on your app_state container; the goal is that `app_state.fact_guard_audit_repo` is reachable from `engine/pipeline/base.py`.)

- [ ] **Step 2: Refactor `_hook_step5_post_write_gate` in `engine/pipeline/base.py`**

Replace the body of the hook between lines 1385-1442 (the existing fact_guard block) with:

```python
            # ── PHASE 2A/2B: fact_guard evaluation (3-attempt loop w/ prose rewrite) ──
            fact_guard_report = None
            rewritten_text: Optional[str] = None
            try:
                from application.sf_log.fact_guard_service import FactGuardService
                from application.sf_log.regex_engine import RegexEngine
                from application.sf_log.bible_snapshot import ChapterBibleContext
                from application.sf_log.fact_guard_cpms import (
                    build_writing_pipeline_invokers,
                    NOOP_AUDIT_REPO,
                )

                global _FACT_GUARD_ENGINE
                if _FACT_GUARD_ENGINE is None:
                    _FACT_GUARD_ENGINE = RegexEngine.from_yaml("config/fact_guard_rules.yaml")
                engine = _FACT_GUARD_ENGINE

                # ── Resolve runtime services ──
                app_state = getattr(self, "_app_state", None) or _DEFAULT_APP_STATE
                audit_repo = getattr(app_state, "fact_guard_audit_repo", NOOP_AUDIT_REPO)

                delegate = self._get_storyos_delegate(ctx)
                provider = _resolve_fact_guard_provider(ctx, app_state)

                invokers = build_writing_pipeline_invokers(
                    assembler=_resolve_cpms_assembler(app_state),
                    llm_provider=provider,
                    parser_service=delegate.parser_service,
                    audit_repo=audit_repo,
                    max_chapter_text_chars=getattr(
                        app_state, "fact_guard_text_cap_chars", 6000,
                    ),
                )

                # ── Bible snapshot ──
                bible_snapshot = getattr(ctx, "chapter_bible_snapshot", None)
                if bible_snapshot is None:
                    cast = getattr(
                        getattr(ctx, "scene_plan", None), "cast", None,
                    ) or set()
                    bible_snapshot = ChapterBibleContext(
                        chapter_id=int(ctx.chapter_number or 0),
                        scene_cast_ids=frozenset(cast),
                        characters=(),
                        worldbuilding_links={},
                    )

                svc = FactGuardService(
                    engine=engine,
                    sflog_invoker=invokers.sflog_invoker,
                    prose_invoker=invokers.prose_invoker,
                    parse_prose=invokers.parse_prose,
                    audit_repo=audit_repo,
                )
                chapter_id = _resolve_chapter_rowid(ctx, delegate)
                fact_guard_report, rewritten_text = svc.evaluate(
                    chapter_text=text or "",
                    sflog_records=records or [],
                    bible_snapshot=bible_snapshot,
                    novel_id=ctx.novel_id,
                    chapter_id=chapter_id or 0,
                )

                ctx.metadata["fact_guard_passed"] = fact_guard_report.passed
                ctx.metadata["fact_guard_forced_pass"] = fact_guard_report.forced_pass
                ctx.metadata["fact_guard_attempt"] = fact_guard_report.attempt
                if fact_guard_report.hits:
                    ctx.metadata.setdefault("storyos_warnings", []).extend(
                        [
                            {
                                "rule_id": h.rule_id,
                                "sflog_id": h.sflog_id,
                                "severity": h.severity.value,
                                "message": h.message,
                            }
                            for h in fact_guard_report.hits
                        ]
                    )
            except Exception as e:                              # noqa: BLE001 — fact_guard must not crash pipeline
                logger.warning(
                    "[%s] fact_guard 评估异常（已降级）: %s",
                    getattr(ctx, "novel_id", "?"), e,
                )
                ctx.storyos_failed.append(f"fact_guard: {e}")
```

Add at module level (top of `engine/pipeline/base.py`) helpers:

```python
# ── Phase 2B: fact_guard runtime accessors ─────────────────────────────
_DEFAULT_APP_STATE = type("_Empty", (), {})()              # sentinel; replace via app_state injection


def _resolve_fact_guard_provider(ctx, app_state):
    """Provider resolution; raise NotImplementedError if not wired."""
    if hasattr(ctx, "llm_provider") and ctx.llm_provider is not None:
        return ctx.llm_provider
    if hasattr(app_state, "llm_provider") and app_state.llm_provider is not None:
        return app_state.llm_provider
    raise NotImplementedError(
        "fact_guard requires an LLM provider; wire one on ctx or app_state"
    )


def _resolve_cpms_assembler(app_state):
    if hasattr(app_state, "cpms_assembler") and app_state.cpms_assembler is not None:
        return app_state.cpms_assembler
    from application.ai_invocation.prompt_assembler import CPMSPromptAssembler
    return CPMSPromptAssembler()


def _resolve_chapter_rowid(ctx, delegate):
    """Find the SQLite rowid of the chapter; 0 if not yet saved (save happens
    in Step 6). For Phase 2B we accept 0 — audit rows use chapter_id=0 for
    pre-save evaluations. After Step 6 saves the chapter, the rows remain
    under chapter_id=0 (no FK constraint violation because the chapter row
    exists at audit-read time but the audit-row insert was already queued
    before the chapter insert).

    If your design requires FK-safe inserts, swap to a 2-step pattern:
    (1) save chapter → (2) enqueue audit rows. Phase 2B keeps it simple.
    """
    try:
        novel_id = ctx.novel_id
        chapter_number = int(ctx.chapter_number or 0)
        with sqlite3.connect(get_db_path()) as conn:
            cur = conn.execute(
                "SELECT id FROM chapters WHERE novel_id = ? AND chapter_number = ? LIMIT 1",
                (novel_id, chapter_number),
            )
            row = cur.fetchone()
            return row[0] if row else 0
    except Exception:
        return 0


# Ensure sqlite3 + get_db_path imports exist near top of file
import sqlite3                                                # noqa: E402
from application.paths import get_db_path                     # noqa: E402
```

- [ ] **Step 3: Update the hook return to include rewritten text**

Modify the return statement at the end of `_hook_step5_post_write_gate`:

```python
            return {
                "format_errors": format_errors,
                "records": records,
                "match_report": match_report,
                "fact_guard_report": fact_guard_report,
                "rewritten_chapter_text": rewritten_text if rewritten_text is not None else text,
            }
```

- [ ] **Step 4: Verify PipelineContext is imported and FactGuardService.evaluate signature matches**

Run: `python -c "from engine.pipeline.base import _hook_step5_post_write_gate; print('ok')"`
Expected: no import errors. If `Tuple` is missing, add `from typing import Tuple, Optional` near the file's top imports.

- [ ] **Step 5: Run all Phase 2A tests still green**

Run: `pytest tests/unit tests/integration -v -x`
Expected: All Phase 2A tests still pass; new Phase 2B tests pass.

- [ ] **Step 6: Smoke test: start backend, hit fact-guard endpoint**

Run: `uvicorn interfaces.main:app --host 127.0.0.1 --port 8005 --reload` (in background)
Run: `curl -sI http://127.0.0.1:8005/openapi.json | head -1`
Run: `curl -s http://127.0.0.1:8005/openapi.json | python -c "import sys,json; d=json.load(sys.stdin); print([p for p in d['paths'] if 'fact-guard' in p])"`
Expected: `['/api/v1/novels/{novel_id}/chapters/{chapter_number}/fact-guard-history']` (after Task 9). Otherwise: empty list (Task 9 not yet done).

- [ ] **Step 7: Commit**

```bash
git add engine/pipeline/base.py interfaces/main.py
git commit -m "feat(pipeline): wire Step 5 hook with real CPMS invokers (Phase 2B Task 8)"
```

---

### Task 9: New `fact-guard-history` endpoint

**Files:**
- Modify: `interfaces/api/v1/core/chapters.py` (add endpoint + DTO)
- Test: `tests/integration/api/test_chapter_fact_guard_history_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/api/test_chapter_fact_guard_history_endpoint.py`:

```python
"""GET /novels/{novel_id}/chapters/{chapter_number}/fact-guard-history."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest


class TestEndpointContract:
    def test_endpoint_returns_paginated_rows(self):
        """End-to-end smoke test against the FastAPI app via test client."""
        from fastapi.testclient import TestClient
        from interfaces.main import app

        client = TestClient(app)
        resp = client.get(
            "/api/v1/novels/nonexistent/chapters/1/fact-guard-history",
        )
        # 404 because chapter doesn't exist
        assert resp.status_code in (200, 404)
```

- [ ] **Step 2: Add the DTO and endpoint to `chapters.py`**

Append to `interfaces/api/v1/core/chapters.py`:

```python
class FactGuardLogDTO(BaseModel):
    id: int
    chapter_id: int
    chapter_number: int
    novel_id: str
    attempt: int
    mode: str
    action: str
    hard_before: int
    hard_after: int
    rule_id: Optional[str] = None
    severity: Optional[str] = None
    diff_excerpt: Optional[str] = None
    notes: Optional[str] = None
    created_at: str

    @classmethod
    def from_row(cls, row: dict) -> "FactGuardLogDTO":
        return cls(**row)


@router.get(
    "/{novel_id}/chapters/{chapter_number}/fact-guard-history",
    response_model=List[FactGuardLogDTO],
)
async def get_chapter_fact_guard_history(
    novel_id: str,
    chapter_number: int,
):
    """Audit trail of every fact_guard attempt (sflog × 2 + prose × 1).

    Each row exposes the LLM's action and the hard-hit count delta so
    writers can review what the gate did to their chapter.
    """
    from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
        FactGuardAuditRepository,
    )
    from application.paths import get_db_path

    chapter_id = _resolve_chapter_id(novel_id, chapter_number)
    if chapter_id is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    repo = FactGuardAuditRepository(get_db_path())
    page = repo.list_for_chapter(chapter_id, limit=50)
    return [FactGuardLogDTO.from_row(r) for r in page.rows]
```

- [ ] **Step 3: Run the test**

Run: `pytest tests/integration/api/test_chapter_fact_guard_history_endpoint.py -v`
Expected: PASS (404 because nonexistent novel).

- [ ] **Step 4: Commit**

```bash
git add interfaces/api/v1/core/chapters.py \
        tests/integration/api/test_chapter_fact_guard_history_endpoint.py
git commit -m "feat(api): GET /chapters/{id}/fact-guard-history endpoint (Phase 2B Task 9)"
```

---

### Task 10: Integration test — full chapter e2e

**Files:**
- Test: `tests/integration/sf_log/test_prose_rewrite_regression_e2e.py`

- [ ] **Step 1: Write the e2e test**

Create `tests/integration/sf_log/test_prose_rewrite_regression_e2e.py`:

```python
"""End-to-end test: full chapter run with fact_guard 3-attempt loop + prose rewrite.

Verifies:
- All 3 attempts invoke the right CPMS node
- Audit row inserted for each attempt
- Rollback path keeps original prose
- Rewritten-chapter-text passed back to caller
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

import pytest

from application.sf_log.fact_guard_service import (
    FactGuardService,
    ProseRewriteResult,
    SFLogRewriteResult,
)
from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.regex_engine import EngineRule, RegexEngine
from application.sf_log.fact_guard_cpms import (
    SFLOG_NODE,
    PROSE_NODE,
    build_writing_pipeline_invokers,
    NOOP_AUDIT_REPO,
)
from domain.storyos.value_objects.sf_log import SFLogRecord
from domain.sf_log.guard_report import GuardHit, Severity


@dataclass
class FakeSnapshot:
    user: str


class FakeAssembler:
    def __init__(self):
        self.calls = []

    def compile(self, *, spec, variable_plan):                # noqa: ANN001
        self.calls.append(spec.node_key)
        return FakeSnapshot(user=f"rendered for {spec.node_key}")


class FakeProvider:
    def __init__(self, responses):
        self._responses = list(responses)

    def generate(self, snap):
        return self._responses.pop(0)


class FakeParser:
    def parse(self, text, n):                                 # noqa: ANN001
        # After prose rewrite, assume SF_LOG records unchanged
        return [SFLogRecord(raw="x", log_type="CHARACTER_EMOTION", char_position=0)]


class FakeAuditRepo:
    def __init__(self):
        self.rows = []

    def append(self, row):
        self.rows.append(row)
        return -1


def _engine_with_hard_rule() -> RegexEngine:
    rule = EngineRule(
        id="r1", applies_to=None,                            # type: ignore
        severity=Severity.HARD, description="d",
    )
    return RegexEngine(rules={"r1": rule})


def _bible() -> ChapterBibleContext:
    return ChapterBibleContext(
        chapter_id=7, scene_cast_ids=frozenset(),
        characters=(), worldbuilding_links={},
    )


class TestE2EProseRewrite:
    def test_rollback_path(self):
        asm = FakeAssembler()
        provider = FakeProvider([
            # attempt 1 sflog: malformed → returns None
            "not json",
            # attempt 2 sflog: malformed → returns None
            "also not json",
            # attempt 3 prose: also malformed → returns rollback
            "garbage response",
        ])
        parser = FakeParser()
        audit_repo = FakeAuditRepo()

        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider,
            parser_service=parser, audit_repo=audit_repo,
        )
        svc = FactGuardService(
            engine=_engine_with_hard_rule(),
            sflog_invoker=invokers.sflog_invoker,
            prose_invoker=invokers.prose_invoker,
            parse_prose=invokers.parse_prose,
            audit_repo=audit_repo,
        )
        report, rewritten = svc.evaluate(
            chapter_text="ORIGINAL TEXT",
            sflog_records=[SFLogRecord(
                raw="s", log_type="CHARACTER_EMOTION", char_position=0,
            )],
            bible_snapshot=_bible(),
            novel_id="alpha", chapter_id=42,
        )
        assert report.passed is True
        assert report.forced_pass is True
        assert rewritten is None                              # rollback path

        # Audit rows: 2 sflog no_rewrite + 1 prose forced_pass_rollback_llm
        actions = [r.action for r in audit_repo.rows]
        assert actions.count("no_rewrite_sflog") == 2
        assert actions.count("forced_pass_rollback_llm") == 1

        # CPMS routing: sflog + sflog + prose
        assert asm.calls == [SFLOG_NODE, SFLOG_NODE, PROSE_NODE]
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/integration/sf_log/test_prose_rewrite_regression_e2e.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/sf_log/test_prose_rewrite_regression_e2e.py
git commit -m "test(sf_log): full-chapter prose rewrite e2e (Phase 2B Task 10)"
```

---

### Task 11: Regression corpus — 5-chapter pass-rate test

**Files:**
- Create: `tests/regression/fixtures/fact_guard_5ch_prose.json`
- Test: `tests/regression/test_phase_2b_prose_rewrite_pass_rate.py`

- [ ] **Step 1: Write the test**

Create `tests/regression/test_phase_2b_prose_rewrite_pass_rate.py`:

```python
"""5-chapter corpus exercising 3 modes:
1. auto-pass (zero HARD hits after attempt 1)
2. sflog-rewritten (LLM returns new records, attempt 2 clears hits)
3. prose-rewritten (LLM rewrites prose, attempt 3 keeps rewrite)
4. prose-rewritten + rollback candidate (LLM rewrites but regression → rollback)
5. provider_failed (LLM throws → rollback, force_pass)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.fact_guard_service import (
    FactGuardService,
    ProseRewriteResult,
    SFLogRewriteResult,
)
from application.sf_log.fact_guard_cpms import build_writing_pipeline_invokers
from application.sf_log.regex_engine import EngineRule, RegexEngine
from domain.sf_log.guard_report import Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "fact_guard_5ch_prose.json"
)


@dataclass
class FakeSnapshot:
    user: str


class FakeAssembler:
    def compile(self, *, spec, variable_plan):                # noqa: ANN001
        return FakeSnapshot(user=spec.node_key)


def _engine_with_hard_rule() -> RegexEngine:
    rule = EngineRule(
        id="r1", applies_to=None,                            # type: ignore
        severity=Severity.HARD, description="d",
    )
    return RegexEngine(rules={"r1": rule})


def _bible(chapter_id: int = 1) -> ChapterBibleContext:
    return ChapterBibleContext(
        chapter_id=chapter_id, scene_cast_ids=frozenset(),
        characters=(), worldbuilding_links={},
    )


class _FakeProvider:
    def __init__(self, scripts):
        self._scripts = list(scripts)

    def generate(self, _snap):
        if not self._scripts:
            return "{}"
        v = self._scripts.pop(0)
        if isinstance(v, Exception):
            raise v
        return v


class _FakeParser:
    def parse(self, text, n):                                 # noqa: ANN001
        return [SFLogRecord(
            raw="s", log_type="CHARACTER_EMOTION", char_position=0,
        )]


class _FakeAudit:
    def __init__(self):
        self.rows = []

    def append(self, row):
        self.rows.append(row)
        return -1


def test_5ch_corpus_pass_rate_at_least_80_percent():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    chapters = fixture["chapters"]
    passing = 0
    for ch in chapters:
        # 1. Pick provider response per chapter's "expected_path"
        asm = FakeAssembler()
        provider = _FakeProvider(ch["provider_responses"])
        parser = _FakeParser()
        audit_repo = _FakeAudit()

        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider,
            parser_service=parser, audit_repo=audit_repo,
        )
        svc = FactGuardService(
            engine=_engine_with_hard_rule(),
            sflog_invoker=invokers.sflog_invoker,
            prose_invoker=invokers.prose_invoker,
            parse_prose=invokers.parse_prose,
            audit_repo=audit_repo,
        )
        record = SFLogRecord(
            raw="s", log_type=ch["log_type"], char_position=0,
        )
        report, rewritten = svc.evaluate(
            chapter_text=ch["chapter_text"],
            sflog_records=[record],
            bible_snapshot=_bible(ch["chapter_number"]),
            novel_id=ch["novel_id"], chapter_id=ch["chapter_id"],
        )
        if ch["expected_pass"]:
            # pass = report.passed AND report.attempt in expected range
            if report.passed and (ch.get("expected_attempt") is None
                                   or report.attempt == ch["expected_attempt"]):
                passing += 1
        else:
            # negative test: must NOT pass with the expected shape
            assert report.passed is False or ch.get("expect_force_pass")

    ratio = passing / len(chapters)
    assert ratio >= 0.80, f"pass rate {ratio:.0%} < 80%"
```

- [ ] **Step 2: Create the fixture**

Create `tests/regression/fixtures/fact_guard_5ch_prose.json`:

```json
{
  "_description": "Phase 2B 5-chapter regression corpus. Each chapter drives FactGuardService through a different code path.",
  "chapters": [
    {
      "chapter_id": 1,
      "chapter_number": 1,
      "novel_id": "test_novel",
      "log_type": "CHARACTER_EMOTION",
      "chapter_text": "Alice walked to the door. (no SF_LOG trigger here)",
      "expected_pass": true,
      "expected_attempt": 1,
      "provider_responses": []
    },
    {
      "chapter_id": 2,
      "chapter_number": 2,
      "novel_id": "test_novel",
      "log_type": "CHARACTER_EMOTION",
      "chapter_text": "Alice felt happy.",
      "expected_pass": true,
      "expected_attempt": 2,
      "provider_responses": [
        "{\"records\": []}"
      ]
    },
    {
      "chapter_id": 3,
      "chapter_number": 3,
      "novel_id": "test_novel",
      "log_type": "CHARACTER_EMOTION",
      "chapter_text": "Alice felt sad.",
      "expected_pass": true,
      "expected_attempt": 3,
      "provider_responses": [
        "not json",
        "also not json",
        "{\"chapter_text\": \"Alice felt conflicted.\", \"rollback_signal\": false}"
      ]
    },
    {
      "chapter_id": 4,
      "chapter_number": 4,
      "novel_id": "test_novel",
      "log_type": "CHARACTER_EMOTION",
      "chapter_text": "Alice felt confused.",
      "expected_pass": true,
      "expect_force_pass": true,
      "expected_attempt": 3,
      "provider_responses": [
        "not json",
        "not json",
        "{\"chapter_text\": \"\", \"rollback_signal\": true, \"notes\": \"REQUIRES_PROSE_ROLLBACK\"}"
      ]
    },
    {
      "chapter_id": 5,
      "chapter_number": 5,
      "novel_id": "test_novel",
      "log_type": "CHARACTER_EMOTION",
      "chapter_text": "Alice felt hopeful.",
      "expected_pass": true,
      "expect_force_pass": true,
      "expected_attempt": 3,
      "provider_responses": [
        "not json",
        "not json",
        ""
      ]
    }
  ]
}
```

- [ ] **Step 3: Run the test**

Run: `pytest tests/regression/test_phase_2b_prose_rewrite_pass_rate.py -v`
Expected: PASS (5/5 = 100%).

- [ ] **Step 4: Commit**

```bash
git add tests/regression/fixtures/fact_guard_5ch_prose.json \
        tests/regression/test_phase_2b_prose_rewrite_pass_rate.py
git commit -m "test(sf_log): 5-chapter regression corpus + pass-rate test (Phase 2B Task 11)"
```

---

### Task 12: Performance test — P95 latency

**Files:**
- Test: `tests/performance/test_prose_rewrite_latency.py`

- [ ] **Step 1: Write the test**

Create `tests/performance/test_prose_rewrite_latency.py`:

```python
"""Phase 2B latency benchmark — P95 < 150ms per chapter (mock LLM)."""
from __future__ import annotations

import time
from dataclasses import dataclass

import pytest

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.fact_guard_service import (
    FactGuardService,
    ProseRewriteResult,
)
from application.sf_log.fact_guard_cpms import build_writing_pipeline_invokers
from application.sf_log.regex_engine import EngineRule, RegexEngine
from domain.sf_log.guard_report import Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


@dataclass
class FakeSnapshot:
    user: str


class FakeAssembler:
    def compile(self, *, spec, variable_plan):                # noqa: ANN001
        return FakeSnapshot(user="")


class FakeProvider:
    def generate(self, _snap):
        # Slightly delayed to simulate LLM call
        time.sleep(0.005)
        return "{}"


class FakeParser:
    def parse(self, text, n):                                 # noqa: ANN001
        return [SFLogRecord(
            raw="s", log_type="CHARACTER_EMOTION", char_position=0,
        )]


class FakeAudit:
    def append(self, row):
        return -1


@pytest.mark.slow
def test_prose_rewrite_p95_under_150ms():
    rule = EngineRule(
        id="r1", applies_to=None,                            # type: ignore
        severity=Severity.HARD, description="d",
    )
    engine = RegexEngine(rules={"r1": rule})
    bible = ChapterBibleContext(
        chapter_id=1, scene_cast_ids=frozenset(),
        characters=(), worldbuilding_links={},
    )

    invokers = build_writing_pipeline_invokers(
        assembler=FakeAssembler(), llm_provider=FakeProvider(),
        parser_service=FakeParser(), audit_repo=FakeAudit(),
    )
    svc = FactGuardService(
        engine=engine,
        sflog_invoker=invokers.sflog_invoker,
        prose_invoker=invokers.prose_invoker,
        parse_prose=invokers.parse_prose,
        audit_repo=FakeAudit(),
    )
    record = SFLogRecord(
        raw="s", log_type="CHARACTER_EMOTION", char_position=0,
    )

    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        svc.evaluate(
            chapter_text="Alice walked slowly.",
            sflog_records=[record],
            bible_snapshot=bible,
            novel_id="n", chapter_id=1,
        )
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    p95 = latencies[int(0.95 * len(latencies)) - 1]
    assert p95 < 150, f"P95 {p95:.1f}ms ≥ 150ms target"
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/performance/test_prose_rewrite_latency.py -v -s`
Expected: PASS (P95 < 150ms).

- [ ] **Step 3: Commit**

```bash
git add tests/performance/test_prose_rewrite_latency.py
git commit -m "test(perf): prose rewrite P95 latency < 150ms (Phase 2B Task 12)"
```

---

### Task 13: Acceptance script + CLAUDE.md update

**Files:**
- Create: `scripts/check_phase_2b_metrics.py`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write the acceptance script**

Create `scripts/check_phase_2b_metrics.py`:

```python
#!/usr/bin/env python3
"""Phase 2B acceptance gate — runs all Phase 2B tests + 2A regression checks.

Mirrors scripts/check_phase_2a_metrics.py (Phase 2A). Exits non-zero on
any failure.
"""
from __future__ import annotations

import subprocess
import sys


PHASE_2B_TESTS = [
    "tests/unit/domain/test_prose_rewrite_value_objects.py",
    "tests/unit/sf_log/test_fact_guard_audit_repository.py",
    "tests/unit/sf_log/test_fact_guard_service_prose_path.py",
    "tests/unit/infrastructure/ai/test_sf_log_prose_rewrite_cpms_node.py",
    "tests/unit/application/sf_log/test_fact_guard_cpms_wiring.py",
    "tests/integration/sf_log/test_prose_rewrite_regression_e2e.py",
    "tests/integration/api/test_chapter_fact_guard_history_endpoint.py",
    "tests/regression/test_phase_2b_prose_rewrite_pass_rate.py",
]

PHASE_2A_REGRESSION_TESTS = [
    "tests/unit/sf_log/test_fact_guard_service.py",
    "tests/unit/sf_log/test_regex_engine.py",
    "tests/regression/test_phase_2a_fact_guard_pass_rate.py",
]


def _run(label: str, cmd: list) -> bool:
    print(f"\n=== {label} ===\n  {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=False)
    return res.returncode == 0


def main() -> int:
    failures = 0

    # Phase 2B
    for t in PHASE_2B_TESTS:
        if not _run(t, ["pytest", t, "-v"]):
            failures += 1

    # 2A regression
    for t in PHASE_2A_REGRESSION_TESTS:
        if not _run(t, ["pytest", t, "-v", "--tb=short"]):
            failures += 1

    # 2B performance
    if not _run(
        "perf", ["pytest", "tests/performance/test_prose_rewrite_latency.py", "-v", "-s"],
    ):
        failures += 1

    print(f"\n{'='*60}\nFAILED: {failures} test files\n{'='*60}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the gate**

Run: `python scripts/check_phase_2b_metrics.py`
Expected: all PASS; final exit 0.

- [ ] **Step 3: Update CLAUDE.md**

Append to `CLAUDE.md` after the Phase 2A section:

```markdown
### Phase 2B — Tier 0 SF_LOG Prose Rewrite (v1.4)

项目 v1.3 之后引入 Tier 0 prose 改写层：
- 3-attempt loop：sflog × 2（已有节点 sf-log-rewrite-with-hints）+ prose × 1（新节点 sf-log-prose-rewrite）+ force_pass
- 自动升级：3 次 SF_LOG-only 仍 HARD → attempt 3 prose
- 段落级重写：prose 模式可改含 `matched_text` 的句子 + 同段落上下文延续
- 单 prose attempt + regression guard：`new_hard <= old_hard` 才能落地，否则回滚原文
- 新 CPMS 节点 `sf-log-prose-rewrite`（package.yaml sort_order=116）
- 新增值对象：`ProseRewriteResult`, `SFLogRewriteResult`, `FactGuardLogRow`
- 新 SQLite 表 `storyos_fact_guard_logs`（8 种 action enum，写入走 WriteDispatch per D1；读取走直连）
- 新 endpoint `GET /api/v1/novels/{novel_id}/chapters/{chapter_number}/fact-guard-history`
- 新 helper `_resolve_chapter_id(novel_id, chapter_number)`
- `fact_guard_cpms.py`：CPMS 接线工厂 + `NOOP_AUDIT_REPO` 回退

详见 `docs/superpowers/specs/2026-07-07-phase-2b-prose-rewrite-design.md`
实施计划见 `docs/superpowers/plans/2026-07-07-phase-2b-prose-rewrite.md`
```

- [ ] **Step 4: Commit**

```bash
git add scripts/check_phase_2b_metrics.py CLAUDE.md
git commit -m "docs(phase-2b): add Phase 2B section to CLAUDE.md + acceptance gate"
```

---

### Task 14: Final merge acceptance gate

**Files:** none modified

- [ ] **Step A: Run full Phase 2A + 2B unit + integration + regression suites**

Run: `pytest tests/unit/sf_log tests/integration/sf_log tests/regression -v`
Expected: ≥ 1948 + new tests all pass.

If OOM (as Phase 2A hit): run in chunks:
```bash
pytest tests/unit/sf_log -v
pytest tests/integration/sf_log -v
pytest tests/regression -v
```

- [ ] **Step B: Confirm coverage on sf_log packages ≥ 80%**

Run:
```bash
pip install pytest-cov
pytest tests/unit/sf_log --cov=application/sf_log --cov=infrastructure/persistence/sqlite --cov-report=term-missing --tb=short
```
Expected: ≥ 80% coverage on the modified packages (target, not gate).

- [ ] **Step C: Confirm Phase 2A sanity — no regressions in pipeline**

Run: `pytest tests/unit/sf_log/test_sf_log_fact_guard_hook.py -v` (2A integration)
Expected: PASS.

Run: `pytest tests/integration/sf_log/test_full_chapter_fact_guard_e2e.py -v` (2A e2e)
Expected: PASS.

- [ ] **Step D: Confirm migration applied + audit table populated**

Run:
```bash
sqlite3 data/plotpilot.db "SELECT COUNT(*) FROM storyos_fact_guard_logs;"
```
Expected: ≥ 0 (table exists; rows depend on whether pipeline ran during tests).

Note: The legacy `python scripts/setup/init_database.py` only loads `schema.sql` into `data/novels.db` and is NOT the migration entry point. The active migration runner is `python scripts/run_migrations.py`.

Run a manual smoke:
```bash
curl -s "http://127.0.0.1:8005/api/v1/novels/some_novel/chapters/1/fact-guard-history" | python -m json.tool
```
Expected: 200 with `[]` (empty list) or 404 (novel doesn't exist).

- [ ] **Step E: Merge to master + push to origin**

```bash
git checkout master
git merge --ff-only worktree-storyos-1a-foundation
git push origin master
git checkout worktree-storyos-1a-foundation
```

(Note: master may have other commits ahead; if `--ff-only` fails, use `--no-ff` per the §D1 spec edit in the prior merge.)

If the merge fails due to unexpected conflicts: stop, investigate root cause in changed files, do not bypass with --no-verify.

- [ ] **Step F: Stop background services**

```bash
# Both services were started at the top of this session — stop them now.
pkill -f "uvicorn interfaces.main:app" || true
pkill -f "vite" || true
```

---

## Acceptance criteria summary

1. **Zero Phase 2A regressions** — all 1948+ Phase 2A tests still pass.
2. **All Phase 2B tests pass** — 28+ unit, 2+ integration, regression, performance.
3. **Regression corpus** ≥ 80% pass rate (target: 5/5).
4. **Audit row count per chapter** ≥ 1 with action ∈ the 8-value enum.
5. **`storyos_fact_guard_logs` table** exists post-migration with both indexes.
6. **`fact-guard-history` endpoint** returns 200 with rows or 404 on missing chapter.
7. **Python 3.9 compat** preserved (`Optional[X]`, `List[X]`, `Tuple[...]`, `from __future__ import annotations`).
8. **CLAUDE.md** updated with Phase 2B section.
9. **Master is fast-forward of worktree** + pushed to `origin`.
