import pytest
from application.engine.services.circuit_breaker import CircuitBreaker


def test_circuit_breaker_gate_independent_counts():
    """gate A 失败 2 次，gate B 失败 2 次 — 互不影响。"""
    cb = CircuitBreaker(failure_threshold=3)
    # spec §3.6 签名：record_retry(scope_id, gate, hints)
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="missing clue 1")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="missing clue 2")
    cb.record_retry(scope_id=1, gate="fact_guard", hints="fact mismatch")
    cb.record_retry(scope_id=1, gate="fact_guard", hints="fact mismatch")
    # spec §3.6 签名：get_retry_count(scope_id, gate='default')
    assert cb.get_retry_count(scope_id=1, gate="sflog_compliance") == 2
    assert cb.get_retry_count(scope_id=1, gate="fact_guard") == 2


def test_circuit_breaker_record_retry_appends_hints():
    """record_retry 不重置 hints 列表（spec §3.6: hints 是累积的）。"""
    cb = CircuitBreaker(failure_threshold=10)
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="first")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="second")
    hints = cb.get_retry_hints(scope_id=1, gate="sflog_compliance")
    assert hints == ["first", "second"]


def test_circuit_breaker_success_resets_count():
    """record_retry 用 success=True 重置计数（spec §3.6）。"""
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x", success=True)
    assert cb.get_retry_count(scope_id=1, gate="sflog_compliance") == 0


def test_circuit_breaker_gate_separate_tripping():
    """gate A 失败次数达阈值 → 单独 open；gate B 不受影响。"""
    cb = CircuitBreaker(failure_threshold=2)
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    assert cb.is_gate_open(scope_id=1, gate="sflog_compliance") is True
    assert cb.is_gate_open(scope_id=1, gate="fact_guard") is False


def test_circuit_breaker_record_force_pass():
    """spec §3.6 锁定 record_force_pass(scope_id, gate, notes) 必须存在。"""
    cb = CircuitBreaker(failure_threshold=2)
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    # 强制通过
    cb.record_force_pass(scope_id=1, gate="sflog_compliance", notes="LLM unable to satisfy, proceed")
    # 强制通过后 retry_count 重置为 0
    assert cb.get_retry_count(scope_id=1, gate="sflog_compliance") == 0
    assert cb.was_force_passed(scope_id=1, gate="sflog_compliance") is True


def test_circuit_breaker_backward_compat():
    """旧 API（无 gate）应继续工作，不计入 gate 维度。"""
    cb = CircuitBreaker(failure_threshold=3)
    assert cb.is_open() is False
    cb.record_failure()  # 旧 API
    cb.record_failure()
    assert cb.get_retry_count(scope_id=1, gate="default") == 0  # 旧 API 不计入 gate
