import pytest
from application.storyos.services.evolution_bridge_service import (
    EvolutionBridgeService, EvolutionBridgeError,
)
from application.storyos.parsers.sf_log_action_mapper import SFLogActionMapper
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.circuit_breaker_integration import SFLogComplianceGate
from application.engine.services.circuit_breaker import CircuitBreaker
from application.storyos.value_objects.bridge_result import BridgeResult
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


def _location_change_record(char_id="alice"):
    """spec §3.3 锁定的 6 mapped 类型之一（CHARACTER_LOCATION_CHANGE）。"""
    return SFLogRecord(
        log_type=SFLogType.CHARACTER_LOCATION_CHANGE,
        params={"char_id": char_id, "location": "cave"},
        raw="<!-- ... -->", chapter_id=1, char_position=0, asset_id=char_id,
    )


def test_bridge_apply_sflog_batch_atomically(monkeypatch):
    """spec §4.1 Step 6 锁定方法名：apply_sflog_batch。"""
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: True,
    )
    cascade = CascadeService(conflict_svc=ConflictRegistryService())
    bridge = EvolutionBridgeService(
        action_mapper=SFLogActionMapper(),
        cascade_service=cascade,
    )
    result = bridge.apply_sflog_batch(
        novel_id="n1", chapter_id=1, records=[_location_change_record()],
    )
    assert isinstance(result, BridgeResult)
    assert result.chapter_id == 1
    assert result.success is True
    assert result.evolution_actions_applied == 1  # CHARACTER_LOCATION_CHANGE 映射到 MOVE_CHARACTER


def test_bridge_on_failure_writes_bridge_log_and_invokes_force_pass(monkeypatch):
    """spec §4.3 D 失败模式：ROLLBACK + bridge_log + 调用 force_pass 通知 pipeline。"""
    def fake_enqueue_txn_batch(ops):
        raise RuntimeError("evolution apply failed (Evolution reducer rejected)")

    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        fake_enqueue_txn_batch,
    )
    cb = CircuitBreaker(failure_threshold=3)
    gate = SFLogComplianceGate(circuit_breaker=cb)
    bridge = EvolutionBridgeService(
        action_mapper=SFLogActionMapper(),
        cascade_service=CascadeService(),
        compliance_gate=gate,
    )
    with pytest.raises(EvolutionBridgeError, match="bridge failed"):
        bridge.apply_sflog_batch(
            novel_id="n1", chapter_id=1, records=[_location_change_record()],
        )
    # spec §3.6：bridge 失败后调 compliance gate record_force_pass 通知 pipeline
    assert cb.was_force_passed(scope_id="n1", gate="sflog_compliance") is True