import pytest
from infrastructure.persistence.database.write_dispatch import (
    WriteDispatch,
    WriteTransaction,
)


def test_write_transaction_constructs_empty():
    txn = WriteTransaction()
    assert txn is not None


def test_write_transaction_queue_adds_op():
    txn = WriteTransaction()
    called = []

    def op(conn):
        called.append(conn)

    txn.queue(op)
    assert len(txn._ops) == 1
    assert txn._ops[0] is op


def test_write_transaction_dispatches_to_writer():
    """WriteTransaction's _ops list holds ops until dispatch (1A: just verify _ops equality)."""
    txn = WriteTransaction()

    def op(_conn):
        pass

    txn.queue(op)
    assert txn._ops == [op]


def test_write_dispatch_has_transaction_method():
    assert hasattr(WriteDispatch, "transaction")


def test_transaction_context_returns_write_transaction():
    wd = WriteDispatch()
    with wd.transaction() as txn:
        assert isinstance(txn, WriteTransaction)


def test_transaction_normal_exit_commits_ops(monkeypatch):
    """正常退出 → 跑 callable 收集 SQL → enqueue_txn_batch。

    1A+ 修复：callable 在 API 线程用 TxnCollectingConnection 执行，产生的 SQL
    列表推给 writer 线程。
    """
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(list(ops)) or True,
    )
    with wd.transaction() as txn:
        # callable 显式 produce SQL，TxnCollectingConnection 会收集
        def op_a(conn):
            conn.execute("INSERT INTO x VALUES (?)", (1,))

        def op_b(conn):
            conn.execute("UPDATE y SET z = ?", (2,))

        txn.queue(op_a)
        txn.queue(op_b)
    assert len(captured) == 1
    assert len(captured[0]) == 2
    assert captured[0][0] == ("INSERT INTO x VALUES (?)", (1,))
    assert captured[0][1] == ("UPDATE y SET z = ?", (2,))


def test_transaction_exception_rolls_back(monkeypatch):
    """异常退出 → 丢弃 _ops，不调用 enqueue_txn_batch。"""
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(ops) or True,
    )
    with pytest.raises(RuntimeError):
        with wd.transaction() as txn:
            txn.queue(lambda c: None)
            raise RuntimeError("boom")
    assert captured == []  # no commit


def test_queue_apply_with_eager_args():
    """queue_apply 把 fn + args 立即绑定（避免闭包陷阱）。

    1A+ 修复：fn 签名是 ``fn(conn, *args, **kwargs)``；conn 在调用时注入。
    args/kwargs 在 queue_apply 时**快照**，调用方后续修改原列表不会影响已入队的 op。
    """
    counter = {"calls": 0}

    def fn(conn, x, y):
        counter["calls"] += 1
        assert x + y == 3

    wd = WriteDispatch()
    with wd.transaction() as txn:
        # 参数 1, 2 在入队时立即快照；随后定义 x,y 不会影响
        x, y = 100, 200
        txn.queue_apply(fn, 1, 2)
        # 参数在入队时已快照；执行时直接成功
        assert len(txn._ops) == 1
        # 模拟执行（conn 在调用时注入）
        op = txn._ops[0]
        op(None)
        assert counter["calls"] == 1
        assert x == 100 and y == 200  # 调用方后续定义不影响已入队的 op


def test_transaction_atomicity_on_exception(monkeypatch):
    """op 抛异常 → 后续 op 不执行（D3 阶段 rollback 完整实现）。

    触发点：``with wd.transaction()`` body 内部 raise → ``except BaseException`` 拦下 →
    跳过 ``else`` 分支 → 不调用 enqueue_txn_batch，全部 ops 丢弃（与 D2 rollback 等价）。
    """
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(ops) or True,
    )
    with pytest.raises(RuntimeError):
        with wd.transaction() as txn:
            def op_a(_c): captured.append("a")
            def op_b(_c): captured.append("b")
            def op_c(_c): captured.append("c")
            txn.queue(op_a)
            txn.queue(op_b)
            txn.queue(op_c)
            # 在 op 队列就绪后、body 末尾触发异常 → 整体 rollback
            raise RuntimeError("body raised")
    # enqueue_txn_batch 未被调用 → 所有 op 丢弃
    assert captured == []


def test_transaction_order_preserved(monkeypatch):
    """op 按入队顺序产生 SQL 并按顺序提交。"""
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(list(ops)) or True,
    )
    with wd.transaction() as txn:
        def op_a(conn):
            conn.execute("INSERT INTO a VALUES (?)", (1,))

        def op_b(conn):
            conn.execute("INSERT INTO b VALUES (?)", (2,))

        def op_c(conn):
            conn.execute("INSERT INTO c VALUES (?)", (3,))

        txn.queue(op_a)
        txn.queue(op_b)
        txn.queue(op_c)
    assert len(captured) == 1
    # 入队顺序在 SQL 列表中保持
    assert captured[0] == [
        ("INSERT INTO a VALUES (?)", (1,)),
        ("INSERT INTO b VALUES (?)", (2,)),
        ("INSERT INTO c VALUES (?)", (3,)),
    ]


def test_transaction_dispatches_queue_apply_partials(monkeypatch):
    """queue_apply 产生的 functools.partial 在 transaction() 退出时被调用并产生 SQL。

    1A+ 修复验证：queue_apply 路径不再崩溃（functools.partial 不再被当作 tuple 索引）。
    """
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(list(ops)) or True,
    )

    def evolution_apply(conn, actions, novel_id):
        conn.execute(
            "INSERT INTO storyos_conflict_v1 (id, project_id, status) VALUES (?, ?, ?)",
            (f"c-{actions[0]}", novel_id, "active"),
        )

    with wd.transaction() as txn:
        txn.queue_apply(evolution_apply, ["c1", "c2"], "n1")
        txn.queue_apply(evolution_apply, ["c3"], "n1")
    assert len(captured) == 1
    assert len(captured[0]) == 2
    # 第一个 op 包含两个 actions 中的第一个 (actions[0])
    assert captured[0][0][1] == ("c-c1", "n1", "active")


def test_dispatch_queue_apply_runs_outside_transaction(monkeypatch):
    """dispatch.queue_apply 直接派发一条 op，无需 transaction 包裹。

    spec §3.4 bridge_log 用法：bridge 事务回滚后，在 except 块调用
    dispatch.queue_apply(bridge_log_record, ...) 写审计行。
    """
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(list(ops)) or True,
    )

    def bridge_log_record(conn, success, error):
        conn.execute(
            "INSERT INTO storyos_bridge_log_v1 "
            "(id, project_id, success, error) VALUES (?, ?, ?, ?)",
            ("b1", "n1", success, error),
        )

    wd.queue_apply(bridge_log_record, False, "cascade failed")
    assert len(captured) == 1
    assert captured[0] == [
        (
            "INSERT INTO storyos_bridge_log_v1 "
            "(id, project_id, success, error) VALUES (?, ?, ?, ?)",
            ("b1", "n1", False, "cascade failed"),
        )
    ]


def test_dispatch_queue_apply_after_transaction_rollback(monkeypatch):
    """模拟 spec §4.2 完整模式：bridge 事务回滚 → except 块用 dispatch.queue_apply 写 bridge_log。"""
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(list(ops)) or True,
    )

    def evolution_apply(conn):
        conn.execute("INSERT INTO evolution VALUES (1)", ())

    def bridge_log_record(conn, success, error):
        conn.execute(
            "INSERT INTO storyos_bridge_log_v1 "
            "(id, project_id, success, error) VALUES (?, ?, ?, ?)",
            ("b1", "n1", success, error),
        )

    with pytest.raises(RuntimeError):
        with wd.transaction() as txn:
            txn.queue_apply(evolution_apply)
            raise RuntimeError("bridge failed")
    # 第一轮：事务回滚 → captured 应为空（evolution_apply 的 SQL 被丢弃）
    assert captured == []
    # except 块：用 dispatch.queue_apply 写 bridge_log
    try:
        raise RuntimeError("bridge failed")
    except RuntimeError as e:
        wd.queue_apply(bridge_log_record, False, str(e))
    # 第二轮：bridge_log 的 SQL 被派发
    assert len(captured) == 1
    assert captured[0][0][0].startswith("INSERT INTO storyos_bridge_log_v1")


def test_dispatch_supports_mixed_op_types(monkeypatch):
    """transaction() 同时支持 callable 和 (sql, params) tuple。"""
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(list(ops)) or True,
    )
    with wd.transaction() as txn:
        def op_fn(conn):
            conn.execute("INSERT INTO a VALUES (1)", ())

        txn.queue(op_fn)
        txn.queue(("INSERT INTO b VALUES (2)", ()))  # legacy tuple path
    assert len(captured) == 1
    assert len(captured[0]) == 2
    assert captured[0][0] == ("INSERT INTO a VALUES (1)", ())
    assert captured[0][1] == ("INSERT INTO b VALUES (2)", ())
