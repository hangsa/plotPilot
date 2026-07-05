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


CursorProvider = Callable[[str, tuple], Any]


class LegacyForeshadowingAdapter:
    """旧表只读 adapter（spec Q8）。

    cursor_provider 是注入依赖，方便测试 mock；生产环境传入
    ``lambda sql, params: sqlite_connection.execute(sql, params)``。
    所有方法的 SQL 都通过 ``cursor.execute(SQL, params)`` 触发，
    便于测试侧断言"未触发 INSERT/UPDATE/DELETE/REPLACE/DROP"。

    ``novel_id`` 始终通过 ``params`` 占位符绑定（``WHERE novel_id = ?``），
    严禁字符串拼接到 SQL 中——避免注入风险并与 spec Q8 "只读 adapter"
    的可审计性保持一致。
    """

    _FORBIDDEN_SQL_KEYWORDS = frozenset(["INSERT", "UPDATE", "DELETE", "REPLACE", "DROP"])

    # 9 列 SELECT —— 字段顺序与 schema.sql:537-550 完全对齐。
    # ``novel_id`` 由调用方以 params 形式绑定（见 ``_resolve_cursor``）。
    _SELECT_ALL_SQL = (
        "SELECT id, novel_id, description, planted_chapter, due_chapter, "
        "resolved_chapter, status, importance, subtext_type "
        "FROM foreshadows WHERE novel_id = ? ORDER BY id"
    )
    _COUNT_SQL = "SELECT COUNT(*) FROM foreshadows WHERE novel_id = ?"

    def __init__(self, cursor_provider: CursorProvider) -> None:
        self._cursor_provider = cursor_provider

    def _resolve_cursor(
        self,
        sql: str,
        params: tuple = (),
        cursor: Optional[Any] = None,
    ) -> Any:
        """获取 cursor：优先用调用方注入的（用于测试断言），否则走 cursor_provider。

        无论哪条路径，``params`` 都会绑定到 SQL 占位符上：
        - 注入 cursor：调用 ``target.execute(sql, params)``，无 params 时也带空元组，
          与 sqlite3 的 ``execute(sql)`` 语义一致。
        - cursor_provider：调用方提供的 provider 接收 ``(sql, params)`` 并返回已
          execute 过的 cursor；这里**不再**对其返回对象调用 execute。
        """
        if cursor is not None:
            target = cursor
            target.execute(sql, params)
        else:
            target = self._cursor_provider(sql, params)
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
        ``novel_id`` 以占位符 ``?`` 的形式绑定，不参与字符串拼接。

        Returns:
            (records, invalid_ids): records 是合法行，invalid_ids 是损坏行 ID 列表。
        """
        target = self._resolve_cursor(
            self._SELECT_ALL_SQL, params=(novel_id,), cursor=cursor,
        )
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
        target = self._resolve_cursor(
            self._COUNT_SQL, params=(novel_id,), cursor=cursor,
        )
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
