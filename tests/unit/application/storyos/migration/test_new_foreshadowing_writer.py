"""new_foreshadowing_writer 单元测试（fix C2）。

生产 ``NewForeshadowingWriter.insert_batch`` 走 ``enqueue_txn_batch``(全局
persistence queue), 在单元测试中无法直接触发 SQL. 本测试的策略:

1. 通过 monkey-patch 把 ``enqueue_txn_batch`` 替换为"在临时 SQLite 连接上
   直接 execute" 的 stub, 捕获 (sql, params) 后真正跑 SQL. 临时连接上预先
   应用生产 ``storyos_init_0001.upgrade()``, schema 与生产完全一致.
2. 验证 INSERT 写入的列名 / 值与生产 DDL 严格对齐 (fix C2 锁定):
   - ``planted_in_chapter`` 来自 ``LegacyForeshadowingRecord.planted_chapter``
   - ``suggested_resolve_chapter`` 来自 ``rec.due_chapter``
   - ``resolved_in_chapter`` 来自 ``rec.resolved_chapter``
   - ``importance`` 是 ``str(rec.importance)`` (TEXT 列)
   - ``created_chapter`` = ``rec.planted_chapter``
   - ``linked_assets`` = ``'{}'``
   - ``cascade_updated_at`` = NULL
   - ``migrated_from_legacy_id`` = ``rec.id``
3. 通过真 SQL 验证 UNIQUE 约束的幂等性.
4. 验证 ``delete_by_migrated_ids`` 返回 ``cursor.rowcount`` (不是 ``len(old_ids)``).
"""
from __future__ import annotations

import sqlite3
import threading
from typing import Any, Callable, List, Optional

import pytest

from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingRecord,
)
from application.storyos.migration.new_foreshadowing_writer import (
    NewForeshadowingWriter,
)
from domain.storyos.contracts import AssetStatus


# ---------------------------------------------------------------------------
# Shared in-memory DB + capture harness for WriteDispatch monkey-patch
# ---------------------------------------------------------------------------


class _InMemoryDB:
    """In-memory SQLite + threading.Lock, mirroring e2e fixture."""

    def __init__(self) -> None:
        self._conn = sqlite3.connect(
            ":memory:", check_same_thread=False, isolation_level=None,
        )
        self._lock = threading.Lock()

    def execute(self, sql, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            return cur

    def executemany(self, sql, seq):
        with self._lock:
            return self._conn.executemany(sql, seq)

    def executescript(self, sql):
        with self._lock:
            self._conn.executescript(sql)

    def commit(self):
        return None

    def close(self):
        with self._lock:
            self._conn.close()

    @property
    def raw_conn(self) -> sqlite3.Connection:
        return self._conn


@pytest.fixture
def prod_schema_db(monkeypatch) -> _InMemoryDB:
    """返回带生产 schema 的 in-memory DB, 并 monkey-patch WriteDispatch."""
    from infrastructure.persistence.database.migrations.versions import (
        storyos_init_0001,
    )
    db = _InMemoryDB()
    storyos_init_0001.upgrade(db.raw_conn)

    # capture (sql, params) so tests can also assert parameter values
    captured: List = []
    last_rowcount: List = [0]

    def _fake_enqueue(operations):
        last_rowcount[0] = 0
        for sql, params in operations:
            cur = db.execute(sql, params)
            captured.append((sql, params, cur))
            last_rowcount[0] += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
        db.commit()
        # 透传真实 rowcount, 让 delete_by_migrated_ids 拿到 cursor.rowcount。
        return last_rowcount[0]

    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        _fake_enqueue,
    )
    monkeypatch.setattr(
        "application.storyos.migration.new_foreshadowing_writer.enqueue_txn_batch",
        _fake_enqueue,
    )
    db._captured = captured  # type: ignore[attr-defined]
    return db


def _row_for_legacy(rec_id: str = "fs-1") -> LegacyForeshadowingRecord:
    return LegacyForeshadowingRecord(
        id=rec_id,
        novel_id="novel-test",
        description="主角得到神秘信件",
        planted_chapter=5,
        due_chapter=12,
        resolved_chapter=20,
        status="resolved",
        importance=4,
        subtext_type=None,
    )


# ---------------------------------------------------------------------------
# Tests (TDD red-green for fix C2)
# ---------------------------------------------------------------------------


def test_insert_batch_uses_production_column_names(prod_schema_db):
    """insert_batch 写入的列名 / 列值必须与生产 DDL 严格对齐 (fix C2).

    关键约束:
    - SQL 中不应出现 ``asset_type`` / ``planted_chapter`` / ``payoff_chapter``
      / ``resolved_chapter`` / ``created_at=`` 显式传值
    - 应出现生产列: ``planted_in_chapter`` / ``suggested_resolve_chapter`` /
      ``resolved_in_chapter`` / ``importance`` / ``migrated_from_legacy_id``
    - 写入后 ``SELECT *`` 返回的列值正确
    """
    rec = _row_for_legacy("fs-1")
    status = AssetStatus.RESOLVED

    writer = NewForeshadowingWriter()
    writer.insert_batch([rec], [status])

    # 1. SQL 字面量断言 (拦截坏列名漂移)
    assert len(prod_schema_db._captured) == 1
    sql, params, _cur = prod_schema_db._captured[0]

    # 旧版错误列名不应再出现
    forbidden = ["asset_type", "planted_chapter", "payoff_chapter",
                 "resolved_chapter"]
    for kw in forbidden:
        assert kw not in sql, (
            f"INSERT SQL 仍含错误列名 '{kw}':\n{sql}"
        )

    # 生产列必须出现
    required = [
        "planted_in_chapter", "suggested_resolve_chapter",
        "resolved_in_chapter", "importance",
        "migrated_from_legacy_id", "created_chapter",
        "linked_assets", "cascade_updated_at",
    ]
    for kw in required:
        assert kw in sql, (
            f"INSERT SQL 缺少生产列 '{kw}':\n{sql}"
        )

    # 2. params 顺序 / 值断言 (匹配 spec 字段映射)
    # INSERT 列顺序按生产 writer:
    # id, project_id, created_chapter, status, description,
    # linked_assets, cascade_updated_at, importance,
    # planted_in_chapter, suggested_resolve_chapter, resolved_chapter,
    # migrated_from_legacy_id
    assert params[0] == "mig-fs-1"           # id (mig- 前缀)
    assert params[1] == "novel-test"          # project_id
    assert params[2] == 5                     # created_chapter = planted_chapter
    assert params[3] == AssetStatus.RESOLVED.value  # status
    assert params[4] == "主角得到神秘信件"     # description
    assert params[5] == "{}"                  # linked_assets
    assert params[6] is None                  # cascade_updated_at
    assert params[7] == "4"                   # importance (str!)
    assert params[8] == 5                     # planted_in_chapter
    assert params[9] == 12                    # suggested_resolve_chapter
    assert params[10] == 20                   # resolved_chapter
    assert params[11] == "fs-1"               # migrated_from_legacy_id

    # 3. 行实际写入并字段正确
    row = prod_schema_db.raw_conn.execute(
        "SELECT id, project_id, created_chapter, status, description, "
        "linked_assets, cascade_updated_at, importance, planted_in_chapter, "
        "suggested_resolve_chapter, resolved_in_chapter, "
        "migrated_from_legacy_id "
        "FROM storyos_foreshadowing_v1 WHERE id = ?",
        ("mig-fs-1",),
    ).fetchone()

    assert row is not None, "INSERT 后行不存在"
    assert row[0] == "mig-fs-1"
    assert row[1] == "novel-test"
    assert row[2] == 5
    assert row[3] == AssetStatus.RESOLVED.value
    assert row[4] == "主角得到神秘信件"
    assert row[5] == "{}"
    assert row[6] is None
    assert row[7] == "4"  # importance stored as TEXT
    assert row[8] == 5
    assert row[9] == 12
    assert row[10] == 20
    assert row[11] == "fs-1"

    # created_at 由 DEFAULT CURRENT_TIMESTAMP 填充, 不为 NULL
    created_at = prod_schema_db.raw_conn.execute(
        "SELECT created_at FROM storyos_foreshadowing_v1 WHERE id = ?",
        ("mig-fs-1",),
    ).fetchone()[0]
    assert created_at is not None, (
        "created_at 未由 DEFAULT 填充 — writer 不应显式传 created_at"
    )


def test_idempotency_via_unique_constraint(prod_schema_db):
    """UNIQUE(project_id, migrated_from_legacy_id) 阻止重复插入。

    同 rec.id 跑两次 insert_batch, INSERT OR IGNORE 让第二次跳过, 表中只有 1 行。
    """
    rec = _row_for_legacy("fs-dup")

    writer = NewForeshadowingWriter()
    writer.insert_batch([rec], [AssetStatus.PLANTED])
    writer.insert_batch([rec], [AssetStatus.PLANTED])  # should be ignored

    count = prod_schema_db.raw_conn.execute(
        "SELECT COUNT(*) FROM storyos_foreshadowing_v1 "
        "WHERE migrated_from_legacy_id = ?",
        ("fs-dup",),
    ).fetchone()[0]
    assert count == 1, "UNIQUE 约束未生效 — 重复 INSERT 产生了多行"


def test_delete_by_migrated_ids_returns_actual_rowcount(prod_schema_db):
    """delete_by_migrated_ids 应返回真实删除行数 (cursor.rowcount)。

    旧实现错误地返回 ``len(old_ids)``. 修复后: 插入 3 条, 删 2 条 → 返回 2.
    """
    writer = NewForeshadowingWriter()

    # 1. 插 3 条
    records = [
        _row_for_legacy("fs-a"),
        _row_for_legacy("fs-b"),
        _row_for_legacy("fs-c"),
    ]
    writer.insert_batch(records, [AssetStatus.PLANTED] * 3)

    count_before = prod_schema_db.raw_conn.execute(
        "SELECT COUNT(*) FROM storyos_foreshadowing_v1"
    ).fetchone()[0]
    assert count_before == 3

    # 2. 删 2 条 (传入 [fs-a, fs-b], 期望返回 2)
    deleted = writer.delete_by_migrated_ids(["fs-a", "fs-b"])

    # 3. 返回值必须是真实 rowcount, 不是 len(old_ids)
    assert deleted == 2, (
        f"delete_by_migrated_ids 应返回 cursor.rowcount (2), got {deleted}"
    )

    count_after = prod_schema_db.raw_conn.execute(
        "SELECT COUNT(*) FROM storyos_foreshadowing_v1"
    ).fetchone()[0]
    assert count_after == 1

    remaining = prod_schema_db.raw_conn.execute(
        "SELECT migrated_from_legacy_id FROM storyos_foreshadowing_v1"
    ).fetchone()[0]
    assert remaining == "fs-c"


def test_delete_by_migrated_ids_empty_input_returns_zero(prod_schema_db):
    """空列表短路返回 0, 不触发任何 SQL。"""
    writer = NewForeshadowingWriter()
    assert writer.delete_by_migrated_ids([]) == 0
    assert prod_schema_db._captured == []  # no SQL issued


def test_insert_batch_validates_length_match(prod_schema_db):
    """records / statuses 长度不一致抛 ValueError, 不写 DB。"""
    writer = NewForeshadowingWriter()
    rec = _row_for_legacy("fs-x")
    with pytest.raises(ValueError, match="length mismatch"):
        writer.insert_batch([rec], [AssetStatus.PLANTED, AssetStatus.RESOLVED])
    assert prod_schema_db._captured == []


def test_importance_stored_as_text(prod_schema_db):
    """importance 是 TEXT 列 — 写入必须 str(int).

    LegacyForeshadowingRecord.importance 是 int; 若 writer 传 int,
    sqlite3 会做 type coercion 但语义不显式. spec 锁定 ``importance TEXT``,
    因此 writer 必须显式 ``str(rec.importance)``。
    """
    rec = LegacyForeshadowingRecord(
        id="fs-imp", novel_id="novel-imp",
        description="desc", planted_chapter=1,
        due_chapter=None, resolved_chapter=None,
        status="planted", importance=7, subtext_type=None,
    )
    writer = NewForeshadowingWriter()
    writer.insert_batch([rec], [AssetStatus.PLANTED])

    # SQL 参数位置: index 7 是 importance (按生产列顺序)
    sql, params, _ = prod_schema_db._captured[0]
    importance_param = params[7]
    assert isinstance(importance_param, str), (
        f"importance param must be str, got {type(importance_param).__name__}"
    )
    assert importance_param == "7"

    # DB 中 stored value 也是 TEXT
    row = prod_schema_db.raw_conn.execute(
        "SELECT importance, typeof(importance) FROM storyos_foreshadowing_v1 "
        "WHERE id = ?",
        ("mig-fs-imp",),
    ).fetchone()
    assert row[0] == "7"
    assert row[1] == "text", (
        f"importance column must be TEXT type, got {row[1]}"
    )