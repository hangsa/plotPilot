import pytest
from application.storyos.services.circuit_breaker_integration import (
    SFLogComplianceGate, ComplianceDecision,
)
from application.engine.services.circuit_breaker import CircuitBreaker
from domain.storyos.value_objects.predeclared import PredeclaredChange, PredeclaredChanges
from domain.storyos.value_objects.sf_log import SFLogRecord
from domain.storyos.contracts import SFLogType


def _predeclared(asset_id="m1"):
    return PredeclaredChange(log_type=SFLogType.MYSTERY_CLUE, asset_type="mystery", asset_id=asset_id)


def _record(asset_id="m1"):
    return SFLogRecord(
        log_type=SFLogType.MYSTERY_CLUE, params={"mystery_id": asset_id, "content": "x"},
        raw="<!-- ... -->", chapter_id=1, char_position=0, asset_id=asset_id,
    )


def test_compliance_pass_when_perfect_match():
    cb = CircuitBreaker(failure_threshold=3)
    gate = SFLogComplianceGate(circuit_breaker=cb)
    predeclared = PredeclaredChanges(items=[_predeclared()])
    records = [_record()]
    decision = gate.evaluate(predeclared=predeclared, records=records, scope_id=1)
    assert decision == ComplianceDecision.PASS


def test_compliance_retry_when_predeclared_missing_below_threshold():
    """spec §4.4：missing + retry_count < 3 → RETRY（带 hint）。"""
    cb = CircuitBreaker(failure_threshold=3)
    gate = SFLogComplianceGate(circuit_breaker=cb)
    predeclared = PredeclaredChanges(items=[_predeclared()])
    decision = gate.evaluate(predeclared=predeclared, records=[], scope_id=1)
    assert decision == ComplianceDecision.RETRY
    # spec §3.6 锁定 record_retry(scope_id, gate, hints) 累积 hints
    hints = cb.get_retry_hints(scope_id=1, gate="sflog_compliance")
    assert len(hints) >= 1


def test_compliance_warn_when_only_unexpected():
    """spec §4.4：unexpected（无 missing）→ WARN_AND_PASS。"""
    cb = CircuitBreaker(failure_threshold=3)
    gate = SFLogComplianceGate(circuit_breaker=cb)
    predeclared = PredeclaredChanges(items=[])
    records = [_record()]
    decision = gate.evaluate(predeclared=predeclared, records=records, scope_id=1)
    assert decision == ComplianceDecision.WARN


def test_compliance_force_pass_after_retry_threshold():
    """spec §4.4：missing + retry_count >= 3 → FORCE_PASS（带 compatibility_notes）。"""
    cb = CircuitBreaker(failure_threshold=3)
    gate = SFLogComplianceGate(circuit_breaker=cb)
    predeclared = PredeclaredChanges(items=[_predeclared()])
    # 3 次 RETRY
    for _ in range(3):
        gate.evaluate(predeclared=predeclared, records=[], scope_id=1)
    # 第 4 次：force_pass
    decision = gate.evaluate(predeclared=predeclared, records=[], scope_id=1)
    assert decision == ComplianceDecision.FORCE_PASS