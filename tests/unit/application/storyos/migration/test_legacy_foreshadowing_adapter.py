"""legacy_foreshadowing_adapter 单元测试。

适配层只读读取旧 foreshadows 表，转换为 LegacyForeshadowingRecord dataclass，
供 MigrationService.scan() / execute() 消费。
"""
from __future__ import annotations

import sqlite3
from typing import Any

from unittest.mock import MagicMock
import pytest

from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingAdapter,
    LegacyForeshadowingRecord,
)


@pytest.fixture
def fake_db_cursor():
    """模拟 SQLite cursor，返回旧表行数据。"""
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        # 旧表 schema.sql:537-550 字段顺序
        ("fs-1", "novel-1", "主角得到神秘信件", 5, None, None, "planted", 3, None),
        ("fs-2", "novel-1", "反派首次露面", 3, 10, 12, "resolved", 4, None),
        ("fs-3", "novel-1", "被废弃的支线", 7, None, None, "abandoned", 1, None),
    ]
    return cursor


def test_legacy_record_dataclass_fields():
    """LegacyForeshadowingRecord 字段集：8 字段对应旧表列。"""
    rec = LegacyForeshadowingRecord(
        id="fs-1",
        novel_id="novel-1",
        description="desc",
        planted_chapter=5,
        due_chapter=None,
        resolved_chapter=None,
        status="planted",
        importance=3,
        subtext_type=None,
    )
    assert rec.id == "fs-1"
    assert rec.planted_chapter == 5
    assert rec.importance == 3


def test_fetch_all_returns_records(fake_db_cursor):
    """adapter.fetch_all_for_novel 读取所有记录。"""
    adapter = LegacyForeshadowingAdapter(
        cursor_provider=lambda _sql, _params: fake_db_cursor
    )
    records = adapter.fetch_all_for_novel("novel-1")
    assert len(records) == 3
    assert records[0].id == "fs-1"
    assert records[1].status == "resolved"
    assert records[2].status == "abandoned"


def test_fetch_all_returns_empty_when_no_records():
    """空表返回空列表（不抛异常）。"""
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    adapter = LegacyForeshadowingAdapter(
        cursor_provider=lambda _sql, _params: cursor
    )
    assert adapter.fetch_all_for_novel("novel-empty") == []


def test_count_for_novel_uses_select_count():
    """count_for_novel 走 SELECT COUNT(*) 路径，不拉全量数据。"""
    cursor = MagicMock()
    cursor.fetchone.return_value = (42,)
    adapter = LegacyForeshadowingAdapter(
        cursor_provider=lambda _sql, _params: cursor
    )
    assert adapter.count_for_novel("novel-1") == 42


def test_fetch_all_skips_corrupted_rows_gracefully(fake_db_cursor):
    """字段损坏（如 importance 不是 int）→ 跳过该行 + 记录到 invalid_ids。

    降级策略：单行损坏不阻断整个 fetch。
    """
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        ("fs-good", "novel-1", "good", 1, None, None, "planted", 2, None),
        ("fs-bad", "novel-1", "bad", 1, None, None, "planted", "NOT_AN_INT", None),  # 类型错
        ("fs-good2", "novel-1", "good2", 2, None, None, "planted", 3, None),
    ]
    adapter = LegacyForeshadowingAdapter(
        cursor_provider=lambda _sql, _params: cursor
    )
    records, invalid_ids = adapter.fetch_all_with_invalid("novel-1")
    assert len(records) == 2
    assert records[0].id == "fs-good"
    assert "fs-bad" in invalid_ids


def test_adapter_does_not_modify_legacy_table():
    """adapter 严禁执行 INSERT/UPDATE/DELETE —— 通过白名单验证。

    这是 spec Q8 "旧表只读" 约束的代码层强制。
    """
    forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "REPLACE", "DROP"]
    captured_sqls: list = []
    provider_calls: list = []

    def _fake_provider(sql: str, params: tuple) -> Any:
        provider_calls.append((sql, params))
        cursor = MagicMock()

        def _capture(executed_sql, executed_params=()):
            captured_sqls.append(executed_sql)

        cursor.execute.side_effect = _capture
        cursor.fetchall.return_value = []
        cursor.fetchone.return_value = (0,)
        return cursor

    adapter = LegacyForeshadowingAdapter(cursor_provider=_fake_provider)
    adapter.fetch_all_for_novel("novel-1")
    adapter.count_for_novel("novel-1")

    # cursor_provider 拿到了完整的 (sql, params)，绑定路径生效。
    assert len(provider_calls) == 2
    for sql, params in provider_calls:
        assert sql.count("?") == len(params), (
            f"binding count mismatch: ?={sql.count('?')} params={len(params)} sql={sql}"
        )

    for sql in captured_sqls + [s for s, _ in provider_calls]:
        sql_upper = sql.upper()
        for kw in forbidden_keywords:
            assert kw not in sql_upper, f"forbidden keyword {kw} in: {sql}"


def test_resolve_cursor_binds_novel_id_param():
    """C4 regression test：真实 sqlite3 连接下，fetch_all_with_invalid / count_for_novel
    必须把 ``novel_id`` 绑定到 ``WHERE novel_id = ?`` 占位符上。

    修复前报 ``sqlite3.ProgrammingError: Incorrect number of bindings supplied``。
    修复后端到端返回正确行数。
    """
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(
            """
            CREATE TABLE foreshadows (
                id TEXT PRIMARY KEY, novel_id TEXT NOT NULL,
                description TEXT NOT NULL, planted_chapter INTEGER NOT NULL,
                due_chapter INTEGER, resolved_chapter INTEGER,
                status TEXT NOT NULL DEFAULT 'planted',
                importance INTEGER NOT NULL DEFAULT 2,
                subtext_type TEXT
            );
            """
        )
        rows_A = [
            (f"fsA-{i}", "A", f"desc-A-{i}", i + 1, None, None, "planted", 2, None)
            for i in range(3)
        ]
        rows_B = [
            (f"fsB-{i}", "B", f"desc-B-{i}", i + 1, None, None, "planted", 2, None)
            for i in range(2)
        ]
        conn.executemany(
            "INSERT INTO foreshadows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows_A + rows_B,
        )
        conn.commit()

        adapter = LegacyForeshadowingAdapter(
            cursor_provider=lambda sql, params: conn.execute(sql, params)
        )

        records, invalid_ids = adapter.fetch_all_with_invalid(novel_id="A")
        assert len(records) == 3
        assert invalid_ids == []
        assert all(r.novel_id == "A" for r in records)

        assert adapter.count_for_novel(novel_id="A") == 3
        assert adapter.count_for_novel(novel_id="B") == 2
    finally:
        conn.close()
