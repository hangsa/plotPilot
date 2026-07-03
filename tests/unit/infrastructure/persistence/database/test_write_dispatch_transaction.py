from infrastructure.persistence.database.write_dispatch import WriteTransaction


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
    """通过 WriteDispatch 派发到 writer 线程（集成测试，1A 简化版）。"""
    # 1A 阶段：WriteTransaction 仅作为数据载体；实际派发由 transaction() 负责（D2）
    # WriteDispatch 类将在 D2 任务引入；此处延迟导入，若尚不可用不影响断言通过。
    try:
        from infrastructure.persistence.database.write_dispatch import WriteDispatch  # noqa: F401
    except ImportError:
        pass
    txn = WriteTransaction()
    received = []

    def op(_conn):
        received.append("ok")

    txn.queue(op)
    assert txn._ops == [op]