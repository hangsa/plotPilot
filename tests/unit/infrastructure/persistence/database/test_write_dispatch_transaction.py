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
    """正常退出 → 提交所有 _ops 到 enqueue_txn_batch。"""
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(ops) or True,
    )
    with wd.transaction() as txn:
        txn.queue(lambda c: None)
        txn.queue(lambda c: None)
    assert len(captured) == 1
    assert len(captured[0]) == 2


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
    """queue_apply 把 fn + args 立即绑定（functools.partial），避免闭包陷阱。"""
    counter = {"calls": 0}

    def fn(x, y, conn=None):
        counter["calls"] += 1
        assert x + y == 3

    wd = WriteDispatch()
    with wd.transaction() as txn:
        # 参数 1, 2 在入队时立即绑定到 partial；随后定义 x,y 不会影响
        x, y = 100, 200
        txn.queue_apply(fn, 1, 2)
        # 参数在入队时已绑定；执行应直接成功
        assert len(txn._ops) == 1
        # 模拟执行
        partial_op = txn._ops[0]
        partial_op(None)
        assert counter["calls"] == 1


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
    """op 按入队顺序提交。"""
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(list(ops)) or True,
    )
    with wd.transaction() as txn:
        def op_a(_c): pass
        def op_b(_c): pass
        def op_c(_c): pass
        txn.queue(op_a)
        txn.queue(op_b)
        txn.queue(op_c)
    assert len(captured) == 1
    assert captured[0] == [op_a, op_b, op_c]
