from infrastructure.persistence.storyos.schemas.base import BaseRegistrySchema
from infrastructure.persistence.storyos.schemas.bridge_log_schema import BridgeLogSchema
from infrastructure.persistence.storyos.schemas.cascade_history_schema import (
    CascadeHistorySchema,
)
from infrastructure.persistence.storyos.schemas.sflog_event_schema import (
    SFLogEventSchema,
)


def test_cascade_history_tablename():
    assert CascadeHistorySchema.__tablename__ == "storyos_cascade_history_v1"


def test_sflog_event_tablename():
    assert SFLogEventSchema.__tablename__ == "storyos_sflog_event_v1"


def test_bridge_log_tablename():
    assert BridgeLogSchema.__tablename__ == "storyos_bridge_log_v1"


def test_cascade_history_fields():
    cols = {c.name for c in CascadeHistorySchema.__table__.columns}
    expected = {"id", "project_id", "chapter_id", "trigger",
                "source_asset_type", "source_asset_id", "target_asset_type",
                "target_asset_id", "executed", "blocked_reason", "executed_at"}
    assert expected.issubset(cols)


def test_sflog_event_fields():
    cols = {c.name for c in SFLogEventSchema.__table__.columns}
    expected = {"id", "project_id", "chapter_id", "raw_text", "log_type",
                "status", "params", "error"}
    assert expected.issubset(cols)


def test_bridge_log_fields():
    """bridge_log 是 ⚡ 关键表：记录 bridge 失败聚合（在事务外写）。"""
    cols = {c.name for c in BridgeLogSchema.__table__.columns}
    expected = {"id", "project_id", "chapter_id", "transaction_id",
                "evolution_actions_count", "registry_updates_count",
                "cascade_steps_count", "success", "error", "duration_ms", "created_at"}
    assert expected.issubset(cols)


def test_bridge_log_does_not_inherit_base_registry():
    """⚡ bridge_log 不继承 BaseRegistrySchema（独立审计表，无 9 个共用字段）。"""
    assert not issubclass(BridgeLogSchema, BaseRegistrySchema)