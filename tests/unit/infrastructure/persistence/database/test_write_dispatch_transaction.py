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