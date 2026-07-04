"""legacy_foreshadowing_adapter —— 旧 foreshadows 表只读读取。

约束（spec Q8 锁定 + spec §6.3 Risk #3 缓解）：
- 严禁任何 INSERT/UPDATE/DELETE/REPLACE/DROP 操作
- 只通过 SELECT 拉取数据，转换为 LegacyForeshadowingRecord dataclass
- 损坏行降级处理（跳过 + 记录到 invalid_ids），不抛异常中断整个 fetch
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple


@dataclass(frozen=True)
class LegacyForeshadowingRecord:
    """旧 foreshadows 表行数据（只读视图）。

    字段对应 schema.sql:537-550 的 9 列：
        id, novel_id, description, planted_chapter, due_chapter,
        resolved_chapter, status, importance, subtext_type
    """
    id: str
    novel_id: str
    description: str
    planted_chapter: int
    due_chapter: Optional[int]
    resolved_chapter: Optional[int]
    status: str
    importance: int
    subtext_type: Optional[str]


CursorProvider = Callable[[str], Any]


class LegacyForeshadowingAdapter:
    """旧表只读 adapter（spec Q8）。

    cursor_provider 是注入依赖，方便测试 mock；生产环境传入
    `lambda sql: sqlite_connection.execute(sql)`。
    所有方法的 SQL 都通过 ``cursor.execute(SQL)`` 触发，
    便于测试侧断言"未触发 INSERT/UPDATE/DELETE/REPLACE/DROP"。
    """

    _FORBIDDEN_SQL_KEYWORDS = frozenset(["INSERT", "UPDATE", "DELETE", "REPLACE", "DROP"])

    # 9 列 SELECT —— 字段顺序与 schema.sql:537-550 完全对齐。
    _SELECT_ALL_SQL = (
        "SELECT id, novel_id, description, planted_chapter, due_chapter, "
        "resolved_chapter, status, importance, subtext_type "
        "FROM foreshadows WHERE novel_id = ? ORDER BY id"
    )
    _COUNT_SQL = "SELECT COUNT(*) FROM foreshadows WHERE novel_id = ?"

    def __init__(self, cursor_provider: CursorProvider) -> None:
        self._cursor_provider = cursor_provider

    def _resolve_cursor(
        self, sql: str, cursor: Optional[Any] = None,
    ) -> Any:
        """获取 cursor：优先用调用方注入的（用于测试断言），否则走 cursor_provider。

        无论哪条路径，SQL 都会经过 ``cursor.execute(SQL)`` —— 测试可通过 mock
        ``cursor.execute`` 拦截真实 SQL 字符串。
        """
        if cursor is not None:
            target = cursor
        else:
            target = self._cursor_provider(sql)
        target.execute(sql)
        return target

    def fetch_all_for_novel(
        self, novel_id: str, cursor: Optional[Any] = None,
    ) -> List[LegacyForeshadowingRecord]:
        records, _ = self.fetch_all_with_invalid(novel_id, cursor=cursor)
        return records

    def fetch_all_with_invalid(
        self, novel_id: str, cursor: Optional[Any] = None,
    ) -> Tuple[List[LegacyForeshadowingRecord], List[str]]:
        """拉取 novel 下所有 foreshadowing 行；损坏行降级到 invalid_ids。

        ``cursor`` 是测试注入点（optional）：传入时直接调用其 ``execute`` 拦截 SQL，
        否则走构造期注入的 ``cursor_provider``。

        Returns:
            (records, invalid_ids): records 是合法行，invalid_ids 是损坏行 ID 列表。
        """
        target = self._resolve_cursor(self._SELECT_ALL_SQL, cursor=cursor)
        # cursor 期望支持参数化查询
        rows = target.fetchall()
        records: List[LegacyForeshadowingRecord] = []
        invalid_ids: List[str] = []
        for row in rows:
            try:
                records.append(self._row_to_record(row))
            except (ValueError, TypeError):
                invalid_ids.append(row[0])  # row[0] = id
        return records, invalid_ids

    def count_for_novel(
        self, novel_id: str, cursor: Optional[Any] = None,
    ) -> int:
        target = self._resolve_cursor(self._COUNT_SQL, cursor=cursor)
        row = target.fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _row_to_record(row: tuple) -> LegacyForeshadowingRecord:
        """row → LegacyForeshadowingRecord，类型校验失败抛 ValueError。"""
        if len(row) != 9:
            raise ValueError(f"Expected 9 columns, got {len(row)}")
        return LegacyForeshadowingRecord(
            id=str(row[0]),
            novel_id=str(row[1]),
            description=str(row[2]),
            planted_chapter=int(row[3]),
            due_chapter=int(row[4]) if row[4] is not None else None,
            resolved_chapter=int(row[5]) if row[5] is not None else None,
            status=str(row[6]),
            importance=int(row[7]),
            subtext_type=str(row[8]) if row[8] is not None else None,
        )
