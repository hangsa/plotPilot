import pytest
from application.storyos.value_objects.bridge_result import BridgeResult
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.cascade import CascadeStep


def test_bridge_result_default_construction():
    """spec §3.2 锁定 14 字段；transaction_id 可为 None。"""
    r = BridgeResult(bridge_id="b1", chapter_id=1, transaction_id=None)
    assert r.bridge_id == "b1"
    assert r.transaction_id is None
    assert r.evolution_actions_applied == 0
    assert r.evolution_actions_skipped == 0
    # spec 锁定：skipped_log_types 是 list[SFLogType]
    assert r.skipped_log_types == []
    assert r.registry_updates_applied == 0
    # spec 锁定：cascade_steps_executed 是 int，cascade_steps_blocked 是 list[CascadeStep]
    assert r.cascade_steps_executed == 0
    assert r.cascade_steps_blocked == []
    assert r.sflog_events_recorded == 0
    assert r.success is False
    assert r.warnings == []
    assert r.duration_ms == 0
    assert r.error is None


def test_bridge_result_full_construction():
    """完整构造：cascade_steps_blocked 用 CascadeStep 对象列表。"""
    from domain.storyos.contracts import CascadeTrigger, AssetStatus
    blocked = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery", source_asset_id="m1",
        target_asset_type="expectation", target_asset_id="e1",
        new_status=AssetStatus.ACTIVE, reason="cycle detected",
    )
    r = BridgeResult(
        bridge_id="b1", chapter_id=3, transaction_id="t1",
        evolution_actions_applied=5, evolution_actions_skipped=1,
        skipped_log_types=[SFLogType.CHARACTER_EMOTION],
        registry_updates_applied=3, cascade_steps_executed=4,
        cascade_steps_blocked=[blocked], sflog_events_recorded=6,
        success=True, warnings=["unexpected sflog"], duration_ms=120,
    )
    assert r.evolution_actions_applied == 5
    assert r.success is True
    assert r.cascade_steps_blocked[0] is blocked
    assert r.skipped_log_types[0] is SFLogType.CHARACTER_EMOTION
