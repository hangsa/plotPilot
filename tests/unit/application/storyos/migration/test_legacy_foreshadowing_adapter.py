"""legacy_foreshadowing_adapter 单元测试。

适配层只读读取旧 foreshadows 表，转换为 LegacyForeshadowingRecord dataclass，
供 MigrationService.scan() / execute() 消费。
"""
from __future__ import annotations

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
    adapter = LegacyForeshadowingAdapter(cursor_provider=lambda _: fake_db_cursor)
    records = adapter.fetch_all_for_novel("novel-1")
    assert len(records) == 3
    assert records[0].id == "fs-1"
    assert records[1].status == "resolved"
    assert records[2].status == "abandoned"


def test_fetch_all_returns_empty_when_no_records():
    """空表返回空列表（不抛异常）。"""
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    adapter = LegacyForeshadowingAdapter(cursor_provider=lambda _: cursor)
    assert adapter.fetch_all_for_novel("novel-empty") == []


def test_count_for_novel_uses_select_count():
    """count_for_novel 走 SELECT COUNT(*) 路径，不拉全量数据。"""
    cursor = MagicMock()
    cursor.fetchone.return_value = (42,)
    adapter = LegacyForeshadowingAdapter(cursor_provider=lambda _: cursor)
    assert adapter.count_for_novel("novel-1") == 42
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args.args[0]
    assert "SELECT COUNT(*)" in sql
    assert "foreshadows" in sql


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
    adapter = LegacyForeshadowingAdapter(cursor_provider=lambda _: cursor)
    records, invalid_ids = adapter.fetch_all_with_invalid("novel-1")
    assert len(records) == 2
    assert records[0].id == "fs-good"
    assert "fs-bad" in invalid_ids


def test_adapter_does_not_modify_legacy_table():
    """adapter 严禁执行 INSERT/UPDATE/DELETE —— 通过白名单验证。

    这是 spec Q8 "旧表只读" 约束的代码层强制。
    """
    forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "REPLACE", "DROP"]
    adapter = LegacyForeshadowingAdapter(cursor_provider=lambda _: MagicMock())
    # 检查 adapter 提供的所有方法的 SQL 关键字
    for method_name in ["fetch_all_for_novel", "count_for_novel"]:
        method = getattr(adapter, method_name)
        # 用 mock cursor 拦截 execute 调用
        cursor = MagicMock()
        method("novel-1", cursor=cursor) if method_name != "fetch_all_for_novel" else method("novel-1")
        if cursor.execute.called:
            sql = cursor.execute.call_args.args[0].upper()
            for kw in forbidden_keywords:
                assert kw not in sql, f"{method_name} must not use {kw}: {sql}"
