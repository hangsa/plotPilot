from infrastructure.persistence.storyos.mappers.cascade_history_mapper import (
    CascadeHistoryMapper, CascadeHistoryEntry,
)
from infrastructure.persistence.storyos.mappers.sflog_event_mapper import (
    SFLogEventMapper, SFLogEventEntry,
)
from infrastructure.persistence.storyos.mappers.bridge_log_mapper import (
    BridgeLogMapper, BridgeLogEntry,
)


def test_cascade_history_executed_round_trip():
    e = CascadeHistoryEntry(
        id="ch1", project_id="n1", chapter_id=5,
        trigger="conflict_escalation",
        source_asset_type="conflict", source_asset_id="c1",
        target_asset_type="expectation", target_asset_id="e1",
        executed=True, blocked_reason=None,
    )
    row = CascadeHistoryMapper.to_orm(e)
    e2 = CascadeHistoryMapper.to_domain(row)
    assert e2 == e


def test_cascade_history_blocked_round_trip():
    e = CascadeHistoryEntry(
        id="ch2", project_id="n1", chapter_id=5,
        trigger="expectation_decay",
        source_asset_type="expectation", source_asset_id="e1",
        target_asset_type="expectation", target_asset_id="e2",
        executed=False, blocked_reason="would_create_cycle",
    )
    row = CascadeHistoryMapper.to_orm(e)
    e2 = CascadeHistoryMapper.to_domain(row)
    assert e2 == e


def test_sflog_event_round_trip():
    e = SFLogEventEntry(
        id="s1", project_id="n1", chapter_id=3,
        raw_text="SF_LOG change_intensity asset_id=conf_3 delta=+30",
        log_type="change_intensity",
        status="applied",
        params={"asset_id": "conf_3", "delta": "+30"},
        error=None,
    )
    row = SFLogEventMapper.to_orm(e)
    e2 = SFLogEventMapper.to_domain(row)
    assert e2 == e


def test_sflog_event_round_trip_with_error():
    e = SFLogEventEntry(
        id="s2", project_id="n1", chapter_id=3,
        raw_text="SF_LOG change_intensity asset_id=missing delta=+30",
        log_type="change_intensity",
        status="error",
        params={"asset_id": "missing", "delta": "+30"},
        error="asset_id not found",
    )
    row = SFLogEventMapper.to_orm(e)
    e2 = SFLogEventMapper.to_domain(row)
    assert e2 == e


def test_bridge_log_success_round_trip():
    e = BridgeLogEntry(
        id="b1", project_id="n1", chapter_id=5,
        transaction_id="tx_42",
        evolution_actions_count=3, registry_updates_count=5,
        cascade_steps_count=2, success=True, error=None, duration_ms=120,
    )
    row = BridgeLogMapper.to_orm(e)
    e2 = BridgeLogMapper.to_domain(row)
    assert e2 == e


def test_bridge_log_failure_round_trip():
    e = BridgeLogEntry(
        id="b2", project_id="n1", chapter_id=6,
        transaction_id="tx_43",
        evolution_actions_count=0, registry_updates_count=0,
        cascade_steps_count=1, success=False,
        error="cascade step would_create_cycle", duration_ms=15,
    )
    row = BridgeLogMapper.to_orm(e)
    e2 = BridgeLogMapper.to_domain(row)
    assert e2 == e