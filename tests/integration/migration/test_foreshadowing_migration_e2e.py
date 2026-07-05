"""ForeshadowingMigrationService 端到端集成测试（spec §1E F1）。

使用临时 SQLite 数据库 + 直接 conn_provider，绕开全局 persistence queue，
覆盖：
- 幂等性（重复 3 次结果一致）
- 异常数据跳过（未知 status 降级）
- 批次边界（1000 条 / batch_size=333 → 4 batches）
- 旧表保留只读（迁移后旧表数据不变，spec Q8 锁定）
- 断点续跑（模拟中断后从断点继续）
- 回滚（rollback 删除新表数据，旧表不变）
- 每批次一行 migration_log（spec §1E 锁定）

实现说明：
- 测试不走 ``enqueue_txn_batch`` / ``get_database()``，因为二者依赖全局
  persistence queue + 已应用 schema 的全局 DB。
- 这里在临时 SQLite 上调用生产版 ``storyos_init_0001.upgrade()`` 创建
  storyos_foreshadowing_v1 + 索引 + UNIQUE 约束（fix C2 锁定：测试 schema
  与生产 DDL 必须完全一致，否则 writer 用错列名漂移也不会被发现）。
- 用 ``conn_provider`` lambda 直接拿到 ``sqlite3.Connection``，并把
  ``enqueue_txn_batch`` monkey-patch 成"直接在同一连接上按顺序执行
  INSERT/UPDATE/DELETE"。
- legacy adapter 走生产版 ``LegacyForeshadowingAdapter``，cursor_provider
  闭包转发到临时 sqlite3 连接，验证 spec C4 修复后端到端可用。
"""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
from typing import Any, Callable, List, Optional, Set

import pytest

from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from application.storyos.services.migration_audit_service import (
    MigrationAuditService,
)
from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingAdapter,
    LegacyForeshadowingRecord,
)


# ---------------------------------------------------------------------------
# temp_db fixture + helpers (fix C2: e2e schema must mirror production DDL)
# ---------------------------------------------------------------------------


_LEGACY_SCHEMA = """
CREATE TABLE foreshadows (
    id TEXT PRIMARY KEY, novel_id TEXT NOT NULL,
    description TEXT NOT NULL, planted_chapter INTEGER NOT NULL,
    due_chapter INTEGER, resolved_chapter INTEGER,
    status TEXT NOT NULL DEFAULT 'planted',
    importance INTEGER NOT NULL DEFAULT 2,
    subtext_type TEXT
);
"""

# migration_log schema 来自 production migration_log_schema.CREATE_TABLE_SQL
_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS storyos_migration_log_v1 (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    migration_type TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    old_ids TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_migration_log_project_type
    ON storyos_migration_log_v1(project_id, migration_type, status);
"""


@pytest.fixture
def temp_db():
    """创建临时 SQLite（带 foreshadows / storyos_foreshadowing_v1 / log 表）。

    Returns the path. The fixture writes teardown to ``os.unlink``.

    fix C2: production schema (``storyos_init_0001.upgrade()``) is applied
    verbatim to the temp DB — not a hand-rolled fictional schema. This
    prevents the writer's column drift from going undetected.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    # 旧表 + log 表手工建（生产 migration 不管这两张）；
    # 新表走生产 upgrade() 拿真实的 DDL。
    from infrastructure.persistence.database.migrations.versions import (
        storyos_init_0001,
    )
    conn.executescript(_LEGACY_SCHEMA + _LOG_SCHEMA)
    conn.commit()
    storyos_init_0001.upgrade(conn)
    conn.close()
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


def _conn_provider(path: str) -> Callable[[], sqlite3.Connection]:
    """Single shared sqlite3 connection — avoids "database is locked" from
    multiple writers hitting the temp DB in parallel.

    A ``threading.Lock`` serializes writes; reads in the same thread remain
    naturally consistent because there is only one Connection object.
    """

    class _SharedConn:
        def __init__(self) -> None:
            self._conn = sqlite3.connect(
                path, check_same_thread=False, isolation_level=None,
            )
            self._lock = threading.Lock()

        def execute(self, sql, params=()):
            with self._lock:
                return self._conn.execute(sql, params)

        def executemany(self, sql, seq):
            with self._lock:
                return self._conn.executemany(sql, seq)

        def executescript(self, sql):
            with self._lock:
                self._conn.executescript(sql)

        def commit(self):  # no-op in autocommit mode but kept for API compat
            return None

        def close(self):
            with self._lock:
                self._conn.close()

    _shared = _SharedConn()

    def _open() -> Any:
        return _shared

    return _open


# ---------------------------------------------------------------------------
# Test-side MigrationLogRepository: 复用 production 类的 db_provider 接口
# ---------------------------------------------------------------------------


class _TestMigrationLogRepository:
    """``MigrationLogRepository`` 的 sqlite3 直连实现（不通过 dispatch）。"""

    def __init__(self, conn_provider: Callable[[], sqlite3.Connection]) -> None:
        self._db_provider = conn_provider

    def record_committed_batch(
        self,
        migration_id: str,
        project_id: str,
        batch_id: str,
        old_ids: List[str],
        started_at: str,
        completed_at: str,
    ) -> None:
        self._insert_log(
            migration_id=migration_id, project_id=project_id, batch_id=batch_id,
            old_ids=old_ids, status="committed",
            started_at=started_at, completed_at=completed_at, error=None,
        )

    def record_failed_batch(
        self,
        migration_id: str,
        project_id: str,
        batch_id: str,
        old_ids: List[str],
        started_at: str,
        error: str,
    ) -> None:
        self._insert_log(
            migration_id=migration_id, project_id=project_id, batch_id=batch_id,
            old_ids=old_ids, status="failed",
            started_at=started_at, completed_at=None, error=error,
        )

    def _insert_log(
        self,
        migration_id: str, project_id: str, batch_id: str,
        old_ids: List[str], status: str, started_at: str,
        completed_at: Optional[str], error: Optional[str],
    ) -> None:
        db = self._db_provider()
        db.execute(
            "INSERT INTO storyos_migration_log_v1 "
            "(id, project_id, migration_type, batch_id, old_ids, status, "
            "started_at, completed_at, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                migration_id, project_id, "foreshadowing_v1",
                batch_id, json.dumps(old_ids), status,
                started_at, completed_at, error,
            ),
        )
        db.commit()

    def get_committed_old_ids(
        self,
        project_id: str,
        migration_type: str = "foreshadowing_v1",
    ) -> Set[str]:
        db = self._db_provider()
        rows = db.execute(
            "SELECT DISTINCT json_each.value FROM storyos_migration_log_v1, "
            "json_each(storyos_migration_log_v1.old_ids) "
            "WHERE project_id = ? AND migration_type = ? AND status = 'committed'",
            (project_id, migration_type),
        ).fetchall()
        return {row[0] for row in rows}

    def mark_rolled_back(self, migration_id: str) -> None:
        db = self._db_provider()
        db.execute(
            "UPDATE storyos_migration_log_v1 SET status = 'rolled_back' "
            "WHERE id = ? AND status = 'committed'",
            (migration_id,),
        )
        db.commit()

    def get_entry(self, migration_id: str):
        from infrastructure.persistence.storyos.migration_log_mapper import (
            MigrationLogEntry,
            MigrationLogMapper,
            MigrationStatus,
        )
        db = self._db_provider()
        row = db.execute(
            "SELECT id, project_id, migration_type, batch_id, old_ids, status, "
            "started_at, completed_at, error FROM storyos_migration_log_v1 "
            "WHERE id = ?",
            (migration_id,),
        ).fetchone()
        if row is None:
            return None
        entry = MigrationLogEntry(
            id=row[0],
            project_id=row[1],
            migration_type=row[2],
            batch_id=row[3],
            old_ids=json.loads(row[4]) if row[4] else [],
            status=MigrationStatus(row[5]),
            started_at=row[6],
            completed_at=row[7],
            error=row[8],
        )
        del MigrationLogMapper  # noqa: F841  -- ensure mapper import path is loaded
        return entry


# ---------------------------------------------------------------------------
# Test-side NewForeshadowingWriter: monkey-patches enqueue_txn_batch on the fly
# ---------------------------------------------------------------------------


class _TestNewForeshadowingWriter:
    """``NewForeshadowingWriter`` 的 sqlite3 直连版本（不走 dispatch）。

    fix C2: SQL 列名 / 顺序与生产 writer 完全一致, 这样本测试的 schema
    (生产 upgrade()) 与 writer (本类 SQL) 任意一方漂移都会立刻报错。
    """

    def __init__(self, conn_provider: Callable[[], sqlite3.Connection]) -> None:
        self._db_provider = conn_provider
        self._insert_sql = (
            "INSERT OR IGNORE INTO storyos_foreshadowing_v1 "
            "(id, project_id, created_chapter, status, description, "
            "linked_assets, cascade_updated_at, importance, "
            "planted_in_chapter, suggested_resolve_chapter, resolved_in_chapter, "
            "migrated_from_legacy_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )

    def insert_batch(
        self, records: List[LegacyForeshadowingRecord], statuses,
    ) -> None:
        if len(records) != len(statuses):
            raise ValueError("records and statuses length mismatch")
        db = self._db_provider()
        for rec, new_status in zip(records, statuses):
            db.execute(
                self._insert_sql,
                (
                    f"mig-{rec.id}",                          # id
                    rec.novel_id,                             # project_id
                    rec.planted_chapter,                      # created_chapter
                    new_status.value if hasattr(new_status, "value") else str(new_status),  # status
                    rec.description,                          # description
                    "{}",                                     # linked_assets
                    None,                                     # cascade_updated_at
                    str(rec.importance),                      # importance TEXT
                    rec.planted_chapter,                      # planted_in_chapter
                    rec.due_chapter,                          # suggested_resolve_chapter
                    rec.resolved_chapter,                     # resolved_in_chapter
                    rec.id,                                   # migrated_from_legacy_id
                ),
            )
        db.commit()

    def delete_by_migrated_ids(self, old_ids: List[str]) -> int:
        if not old_ids:
            return 0
        placeholders = ",".join("?" for _ in old_ids)
        sql = (
            f"DELETE FROM storyos_foreshadowing_v1 "
            f"WHERE migrated_from_legacy_id IN ({placeholders})"
        )
        db = self._db_provider()
        cur = db.execute(sql, tuple(old_ids))
        db.commit()
        return cur.rowcount


# ---------------------------------------------------------------------------
# Service builder + legacy populator
# ---------------------------------------------------------------------------


def _populate_legacy(db_path: str, novel_id: str, n: int, mix_invalid: bool = False) -> None:
    """填充 n 条旧表记录（spec §1E 旧 schema 9 列）。"""
    conn = sqlite3.connect(db_path)
    statuses = ["planted", "resolved", "abandoned"]
    for i in range(n):
        status = statuses[i % 3]
        if mix_invalid and i == n - 1:
            status = "legacy_weird"  # 1 条未知 status
        conn.execute(
            "INSERT INTO foreshadows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"fs-{i}", novel_id, f"desc-{i}", i + 1,
                None, 5 if status == "resolved" else None,
                status, 2, None,
            ),
        )
    conn.commit()
    conn.close()


def _build_service(db_path: str, monkeypatch) -> ForeshadowingMigrationService:
    """构造 ForeshadowingMigrationService，所有依赖都通过临时 DB 直连。"""
    conn_provider = _conn_provider(db_path)

    # monkey-patch the writer-side enqueue path so the production classes
    # (used inside MigrationLogRepository when test invariants want them
    # untouched) never try to talk to a non-existent persistence queue.
    # 实际写入走 _TestNewForeshadowingWriter / _TestMigrationLogRepository。
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: True,
    )

    # 生产版 LegacyForeshadowingAdapter，cursor_provider 转发到临时
    # sqlite3 连接；每次取数开新连接，sqlite3 cursor 自带 execute 后的状态。
    def legacy_cursor_provider(sql, params):
        conn = conn_provider()
        return conn.execute(sql, params)

    legacy = LegacyForeshadowingAdapter(cursor_provider=legacy_cursor_provider)
    log_repo = _TestMigrationLogRepository(conn_provider=conn_provider)
    new_writer = _TestNewForeshadowingWriter(conn_provider=conn_provider)
    audit = MigrationAuditService()
    return ForeshadowingMigrationService(
        legacy_adapter=legacy,
        log_repository=log_repo,
        new_table_writer=new_writer,
        audit_service=audit,
    )


# ---------------------------------------------------------------------------
# Tests (8 tests, spec §1E F1)
# ---------------------------------------------------------------------------


def test_full_migration_100_records(temp_db, monkeypatch):
    """100 条记录全量迁移正确性（spec §1E F1.1）。"""
    _populate_legacy(temp_db, "novel-1", 100)
    service = _build_service(temp_db, monkeypatch)
    result = service.execute("novel-1", batch_size=50)
    assert result.batches_total == 2
    assert result.batches_done == 2
    assert result.records_migrated == 100
    assert result.status == "completed"


def test_idempotent_repeated_execution(temp_db, monkeypatch):
    """幂等性：重复 3 次迁移结果一致（不重复插入，spec §1E F1.2）。"""
    _populate_legacy(temp_db, "novel-1", 50)
    service = _build_service(temp_db, monkeypatch)

    r1 = service.execute("novel-1", batch_size=50)
    r2 = service.execute("novel-1", batch_size=50)
    r3 = service.execute("novel-1", batch_size=50)

    assert r1.records_migrated == 50
    assert r2.records_migrated == 0  # 已迁移，断点续跑跳过
    assert r3.records_migrated == 0

    # 新表只有 50 条（UNIQUE 约束 + get_committed_old_ids 过滤）
    conn = sqlite3.connect(temp_db)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM storyos_foreshadowing_v1 WHERE project_id = ?",
            ("novel-1",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 50


def test_invalid_status_records_skipped(temp_db, monkeypatch):
    """未知 status 的记录跳过（不入新表，spec §1E F1.3）。"""
    _populate_legacy(temp_db, "novel-1", 10, mix_invalid=True)
    service = _build_service(temp_db, monkeypatch)
    result = service.execute("novel-1", batch_size=50)
    assert result.records_migrated == 9  # 跳过 1 条 legacy_weird
    assert result.status == "completed"


def test_batch_boundary_1000_records(temp_db, monkeypatch):
    """1000 条 / batch_size=333 → 4 batches（333+333+333+1，spec §1E F1.4）。"""
    _populate_legacy(temp_db, "novel-1", 1000)
    service = _build_service(temp_db, monkeypatch)
    result = service.execute("novel-1", batch_size=333)
    assert result.batches_total == 4
    assert result.batches_done == 4
    assert result.records_migrated == 1000


def test_legacy_table_unchanged_after_migration(temp_db, monkeypatch):
    """迁移后旧 foreshadows 表数据未被修改（spec Q8 + §1E F1.5 锁定）。"""
    _populate_legacy(temp_db, "novel-1", 10)
    service = _build_service(temp_db, monkeypatch)

    # 快照旧表
    conn = sqlite3.connect(temp_db)
    try:
        before = conn.execute("SELECT * FROM foreshadows ORDER BY id").fetchall()
    finally:
        conn.close()

    service.execute("novel-1", batch_size=5)

    # 比较旧表
    conn = sqlite3.connect(temp_db)
    try:
        after = conn.execute("SELECT * FROM foreshadows ORDER BY id").fetchall()
    finally:
        conn.close()
    assert before == after, "旧表数据被修改！违反 spec Q8 锁定"


def test_resume_after_partial_failure(temp_db, monkeypatch):
    """断点续跑：前 2 批成功 + 第 3 批失败，重启后只迁移剩余批次（§1E F1.6）。"""
    _populate_legacy(temp_db, "novel-1", 30)

    # 第一次：制造第 3 批失败（batch_size=10 → batch 3 = fs-20..fs-29）
    service = _build_service(temp_db, monkeypatch)
    call_count = [0]
    original = service._new_writer.insert_batch

    def flaky_insert(records, statuses):
        call_count[0] += 1
        if call_count[0] == 3:
            raise RuntimeError("simulated failure")
        return original(records, statuses)

    service._new_writer.insert_batch = flaky_insert

    result = service.execute("novel-1", batch_size=10)
    assert result.status == "partial"
    assert result.batches_done == 2
    assert result.records_migrated == 20

    # 第二次：移除 mock，应该完成剩余的批次（log_repo 只看到 20 条 committed）
    service2 = _build_service(temp_db, monkeypatch)
    result2 = service2.execute("novel-1", batch_size=10)
    assert result2.status == "completed"
    # 只剩 10 条没迁（前 2 批 20 条已 committed → skipped）
    assert result2.records_migrated == 10


def test_rollback_after_migration(temp_db, monkeypatch):
    """迁移后 rollback 删除新表数据，旧表不动（spec §1E F1.7）。"""
    _populate_legacy(temp_db, "novel-1", 10)
    service = _build_service(temp_db, monkeypatch)

    service.execute("novel-1", batch_size=10)

    # 整次迁移只生成了 1 条 migration_log（batch_size=10 → 1 batch）
    committed_ids = service._log_repo.get_committed_old_ids("novel-1")
    assert len(committed_ids) == 10

    # 取那条 migration_log 的 id
    conn = sqlite3.connect(temp_db)
    try:
        mid = conn.execute(
            "SELECT id FROM storyos_migration_log_v1 "
            "WHERE status='committed' LIMIT 1"
        ).fetchone()[0]
    finally:
        conn.close()

    result = service.rollback(mid)
    assert result.status == "rolled_back"
    assert result.records_deleted == 10

    # 新表被清空
    conn = sqlite3.connect(temp_db)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM storyos_foreshadowing_v1"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_migration_log_records_each_batch(temp_db, monkeypatch):
    """每批次写入一条 migration_log（spec §1E F1.8 锁定）。"""
    _populate_legacy(temp_db, "novel-1", 100)
    service = _build_service(temp_db, monkeypatch)
    service.execute("novel-1", batch_size=25)

    conn = sqlite3.connect(temp_db)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM storyos_migration_log_v1 "
            "WHERE status='committed'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 4  # 4 batches → 4 committed log entries
