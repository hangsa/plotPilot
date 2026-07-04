"""单写者内核：标记持久化队列消费线程，并对「非 writer 线程」提供入队封装。

SQLite 单机多写竞争者全部经 mp.Queue → 单一消费者线程顺序提交，从源头消除 database is locked。"""
from __future__ import annotations

import contextlib
import functools
import logging
import re
import threading
from typing import Any, List, Optional, Tuple, Union

from infrastructure.persistence.database.write_environment import (
    SQLiteWriteEnvironmentSettings,
)

logger = logging.getLogger(__name__)

_sqlite_writer_thread_ident: Optional[int] = None

# interfaces.main startup：在持久化消费者线程就绪之前允许直连 SQLite（见 startup_sqlite_writes_bypass_queue）
_startup_sqlite_bootstrap_depth = 0


def register_sqlite_writer_thread() -> None:
    global _sqlite_writer_thread_ident
    _sqlite_writer_thread_ident = threading.get_ident()


def clear_sqlite_writer_thread() -> None:
    global _sqlite_writer_thread_ident
    _sqlite_writer_thread_ident = None


def is_sqlite_writer_thread() -> bool:
    return (
        _sqlite_writer_thread_ident is not None
        and threading.get_ident() == _sqlite_writer_thread_ident
    )


@contextlib.contextmanager
def sqlite_writes_bypass_queue():
    """临时允许调用方线程直连 SQLite。

    仅用于启动早期迁移、测试初始化，或必须写后立刻读的轻量交互态。
    注意：上下文内不要使用 ``await``。
    """
    global _startup_sqlite_bootstrap_depth
    _startup_sqlite_bootstrap_depth += 1
    try:
        yield
    finally:
        _startup_sqlite_bootstrap_depth -= 1


@contextlib.contextmanager
def startup_sqlite_writes_bypass_queue():
    """在持久化消费者线程启动前直连 SQLite 的兼容入口。"""
    with sqlite_writes_bypass_queue():
        yield


def allow_direct_sqlite_writes() -> bool:
    """脚本 / 迁移 / 启动早期 bypass / 个别单测可走直连写库；正式运行时默认走队列。"""
    if _startup_sqlite_bootstrap_depth > 0:
        return True
    return SQLiteWriteEnvironmentSettings.from_env().direct_writes


def strip_sql_comments(sql: str) -> str:
    text = re.sub(r"--[^\n]*", "", sql)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text


def sql_is_mutating(sql: str) -> bool:
    s = strip_sql_comments(sql).strip().upper()
    if not s:
        return False
    if s.startswith("WITH"):
        return bool(re.search(r"\b(INSERT|UPDATE|DELETE|REPLACE)\b", s))
    tok = s.split()[0]
    non_mutating = frozenset(
        {
            "SELECT",
            "EXPLAIN",
            "PRAGMA",
            "BEGIN",
            "COMMIT",
            "ROLLBACK",
            "SAVEPOINT",
            "RELEASE",
            "END",
        }
    )
    if tok in non_mutating:
        return False
    return True


Params = Union[tuple, list]


class _EnqueuedStmtCursor:
    """非 writer 线程上 execute(INSERT/UPDATE…) 入队后对调用方的最小兼容。"""

    rowcount = 1

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class TxnCollectingConnection:
    """在 API 线程上收集 SQL，退出 `transaction()` 时一次性 EXECUTE_SQL_TXN_BATCH。"""

    def __init__(self) -> None:
        self.operations: List[Tuple[str, tuple]] = []

    def execute(self, sql: str, params: Any = ()) -> _EnqueuedStmtCursor:
        if isinstance(params, list):
            p: tuple = tuple(params)
        elif isinstance(params, tuple):
            p = params
        else:
            p = (params,)
        self.operations.append((sql, p))
        return _EnqueuedStmtCursor()


def enqueue_execute_sql(sql: str, params: Optional[Params] = None) -> bool:
    from application.engine.services.persistence_queue import (
        get_persistence_queue,
        PersistenceCommandType,
    )

    pq = get_persistence_queue()
    if pq is None or pq.get_queue() is None:
        logger.error("持久化队列未就绪，丢弃写 SQL")
        return False
    plist = list(params) if params is not None else []
    return pq.push(
        PersistenceCommandType.EXECUTE_SQL.value,
        {"sql": sql, "params": plist},
    )


def enqueue_txn_batch(
    operations: List[Tuple[str, Params]],
) -> bool:
    """多语句同一 BEGIN IMMEDIATE 事务提交（高性能、原子）。"""
    from application.engine.services.persistence_queue import (
        get_persistence_queue,
        PersistenceCommandType,
    )

    if not operations:
        return True
    pq = get_persistence_queue()
    if pq is None or pq.get_queue() is None:
        logger.error("持久化队列未就绪，丢弃事务批量写")
        return False
    serializable = [
        {"sql": op[0], "params": list(op[1]) if op[1] is not None else []}
        for op in operations
    ]
    return pq.push(
        PersistenceCommandType.EXECUTE_SQL_TXN_BATCH.value,
        {"operations": serializable},
    )


def enqueue_delete_chapter(chapter_db_id: str) -> bool:
    from application.engine.services.persistence_queue import (
        get_persistence_queue,
        PersistenceCommandType,
    )

    pq = get_persistence_queue()
    if pq is None or pq.get_queue() is None:
        return False
    return pq.push(
        PersistenceCommandType.DELETE_CHAPTER.value,
        {"chapter_db_id": chapter_db_id},
    )


class WriteTransaction:
    """单事务内多 op 容器（spec §3.5 锁定）。

    1A 阶段：仅作为数据载体，事务派发由 WriteDispatch.transaction()（D2）负责。
    1B 阶段：EvolutionBridgeService 会 queue_apply() 三个 op 提交到这里。
    """

    def __init__(self) -> None:
        self._ops: list = []

    def queue(self, op) -> None:
        """向后兼容的 op 入队。

        支持两种 op 形态：
        - ``(sql, params)`` tuple：直接 push 到 writer 线程
        - callable ``fn(conn, *args, **kwargs)``：在事务退出时由
          ``WriteDispatch.transaction()`` 用 ``TxnCollectingConnection`` 调用，
          收集产生的 SQL 后再批量 push
        """
        self._ops.append(op)

    def run(self, executor) -> None:
        """由 WriteDispatch.transaction() 提交时调用（1A 简化版：直接遍历 _ops）。"""
        if not self._ops:
            return
        for op in self._ops:
            op(executor)

    def queue_apply(self, fn, *args, **kwargs) -> None:
        """入队 fn(conn, *args, **kwargs)。

        参数在 queue_apply 调用时**快照**（避免闭包陷阱：调用方后续修改
        原始 args 不会影响已入队的 op）。实际执行时 ``conn`` 作为第一个
        位置参数注入。

        1B 的 EvolutionBridgeService 用此 API 包装 evolution_apply_actions /
        registry_apply_with_cascade / sflog_event_record 三个 op。
        """
        frozen_args = tuple(args)
        frozen_kwargs = dict(kwargs)

        def op(conn):
            return fn(conn, *frozen_args, **frozen_kwargs)

        self._ops.append(op)


def _dispatch_ops(ops: list) -> None:
    """把混合 op 列表转换成 SQL，enqueue_txn_batch 提交到 writer 线程。

    处理流程：
    1. 在 API 线程上用 ``TxnCollectingConnection`` 实例化临时 conn
    2. 遍历 ops：
       - tuple ``(sql, params)``：直接 append 到 conn.operations
       - callable ``fn(conn, ...)``：调用 fn 收集产生的 SQL
    3. 把收集到的 SQL 通过 ``enqueue_txn_batch`` 推给 writer 线程（writer 做 BEGIN IMMEDIATE）

    这一层统一处理使 ``transaction()`` 退出和 ``dispatch.queue_apply()`` 走同一条路径，
    1B 的 EvolutionBridgeService 不必关心 SQL 序列化细节。
    """
    if not ops:
        return
    conn = TxnCollectingConnection()
    for op in ops:
        if isinstance(op, tuple) and len(op) == 2:
            sql, params = op
            conn.execute(sql, params)
        elif callable(op):
            op(conn)
        else:
            raise TypeError(
                f"unsupported op type: {type(op).__name__}; "
                "expected (sql, params) tuple or callable"
            )
    if conn.operations:
        enqueue_txn_batch(conn.operations)


class WriteDispatch:
    """单写者路由门面（spec §3.5 锁定）。

    1A 阶段：transaction() 返回 WriteTransaction 上下文管理器。
    退出 with 块时：正常退出 → 用 TxnCollectingConnection 收集 SQL → enqueue_txn_batch；
    异常退出 → 丢弃 ops（回滚语义）。

    1B 阶段：EvolutionBridgeService 用 ``dispatch.transaction()`` 包装三个 op，
    ``except`` 块用 ``dispatch.queue_apply()`` 单独写 bridge_log（事务外）。
    """

    @contextlib.contextmanager
    def transaction(self):
        """返回 WriteTransaction 上下文；退出 with 块时提交/回滚。

        Yields:
            WriteTransaction: 容器，调用方 queue(op) / queue_apply(fn, ...) 累积操作。

        On normal exit:
            通过 ``_dispatch_ops`` 把 callable 跑在临时 ``TxnCollectingConnection`` 上
            收集 SQL，再 ``enqueue_txn_batch`` 到 writer 线程。

        On exception:
            _ops 丢弃；``enqueue_txn_batch`` 不被调用（回滚语义）。
            调用方可在 except 块用 ``dispatch.queue_apply(bridge_log_record, ...)``
            在事务外补写审计行。
        """
        txn = WriteTransaction()
        try:
            yield txn
        except BaseException:
            # 回滚：丢弃 _ops，不派发
            raise
        else:
            # 提交：callable 在 API 线程跑出 SQL，再批量 push 到 writer
            _dispatch_ops(txn._ops)

    def queue_apply(self, fn, *args, **kwargs) -> None:
        """在事务外单条入队一个 op。

        用于 spec §3.4 约定的 bridge_log 写入路径：bridge 事务回滚后，
        调用方在 except 块调用 ``dispatch.queue_apply(bridge_log_record, ...)``，
        该 op 立即在 API 线程跑出 SQL 并 push 到 writer 线程的 IMMEDIATE 事务。

        与 ``transaction()`` 的区别：不参与任何进行中的事务，无回滚挂钩。
        """
        frozen_args = tuple(args)
        frozen_kwargs = dict(kwargs)

        def op(conn):
            return fn(conn, *frozen_args, **frozen_kwargs)

        _dispatch_ops([op])
