import sqlite3
from pathlib import Path


def test_alembic_upgrade_creates_11_tables(tmp_path):
    """upgrade() 后 11 张表存在。"""
    db_path = tmp_path / "test.db"
    from infrastructure.persistence.database.migrations.versions import storyos_init_0001
    conn = sqlite3.connect(str(db_path))
    try:
        storyos_init_0001.upgrade(conn)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'storyos_%'"
        )
        tables = {row[0] for row in cur.fetchall()}
        expected_tables = {
            "storyos_conflict_v1", "storyos_mystery_v1", "storyos_twist_v1",
            "storyos_promise_v1", "storyos_reveal_v1", "storyos_expectation_v1",
            "storyos_goal_v1", "storyos_foreshadowing_v1",
            "storyos_cascade_history_v1", "storyos_sflog_event_v1",
            "storyos_bridge_log_v1",
        }
        assert expected_tables.issubset(tables), f"missing: {expected_tables - tables}"
    finally:
        conn.close()


def test_alembic_downgrade_drops_all(tmp_path):
    """downgrade 应删除所有 11 张表。"""
    db_path = tmp_path / "test.db"
    from infrastructure.persistence.database.migrations.versions import storyos_init_0001
    conn = sqlite3.connect(str(db_path))
    try:
        storyos_init_0001.upgrade(conn)
        storyos_init_0001.downgrade(conn)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'storyos_%'"
        )
        tables = {row[0] for row in cur.fetchall()}
        assert tables == set()
    finally:
        conn.close()


def test_conflict_table_has_entity_columns(tmp_path):
    """registry 表必须包含 9 个 mixin 字段 + 实体专属字段。"""
    db_path = tmp_path / "test.db"
    from infrastructure.persistence.database.migrations.versions import storyos_init_0001
    conn = sqlite3.connect(str(db_path))
    try:
        storyos_init_0001.upgrade(conn)
        cur = conn.execute("PRAGMA table_info(storyos_conflict_v1)")
        cols = {row[1] for row in cur.fetchall()}
        # 9 个 mixin 字段
        assert {"id", "project_id", "created_chapter", "status", "description",
                "linked_assets", "cascade_updated_at", "created_at",
                "updated_at"}.issubset(cols)
        # 实体专属字段
        assert {"intensity", "involved_characters"}.issubset(cols)
    finally:
        conn.close()


def test_bridge_log_table_has_no_registry_columns(tmp_path):
    """⚡ bridge_log 不应包含 registry 专属字段（status, description, linked_assets 等）。"""
    db_path = tmp_path / "test.db"
    from infrastructure.persistence.database.migrations.versions import storyos_init_0001
    conn = sqlite3.connect(str(db_path))
    try:
        storyos_init_0001.upgrade(conn)
        cur = conn.execute("PRAGMA table_info(storyos_bridge_log_v1)")
        cols = {row[1] for row in cur.fetchall()}
        # 应只含 bridge_log 11 列
        expected = {"id", "project_id", "chapter_id", "transaction_id",
                    "evolution_actions_count", "registry_updates_count",
                    "cascade_steps_count", "success", "error",
                    "duration_ms", "created_at"}
        assert cols == expected, f"got {cols}"
    finally:
        conn.close()


def test_upgrade_creates_migration_log_table(tmp_path):
    """upgrade() 应创建 storyos_migration_log_v1 表 (fix C3)。

    spec: 该表用于 migration 断点续跑 + 审计持久化,
    MigrationLogRepository.record_committed_batch 在生产代码中会 INSERT 进去。
    若 upgrade() 不创建该表, 第一次执行 migration 时会 crash (no such table)。
    """
    db_path = tmp_path / "test.db"
    from infrastructure.persistence.database.migrations.versions import storyos_init_0001
    conn = sqlite3.connect(str(db_path))
    try:
        storyos_init_0001.upgrade(conn)
        cur = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='storyos_migration_log_v1'"
        )
        row = cur.fetchone()
        assert row is not None, (
            "storyos_migration_log_v1 表未被 upgrade() 创建 — "
            "MigrationLogRepository.record_committed_batch 会在生产中 crash"
        )
        # 验证列集合符合 spec
        cur = conn.execute("PRAGMA table_info(storyos_migration_log_v1)")
        cols = {row[1] for row in cur.fetchall()}
        expected = {
            "id", "project_id", "migration_type", "batch_id",
            "old_ids", "status", "started_at", "completed_at", "error",
        }
        assert cols == expected, (
            f"migration_log 列集合不符: extra={cols - expected}, "
            f"missing={expected - cols}"
        )
    finally:
        conn.close()


def test_migration_matches_sa_schema_columns(tmp_path):
    """每个表的 DDL 列集合必须 == SQLAlchemy 声明列集合（防 schema ↔ migration 漂移）。

    覆盖全部 11 张 storyos 表：8 registry + 3 audit。任何一张表的 schema
    增加/删除/重命名字段未同步到 DDL 都会失败。
    """
    db_path = tmp_path / "test.db"
    from infrastructure.persistence.database.migrations.versions import (
        storyos_init_0001,
    )
    from infrastructure.persistence.storyos.schemas.bridge_log_schema import (
        BridgeLogSchema,
    )
    from infrastructure.persistence.storyos.schemas.cascade_history_schema import (
        CascadeHistorySchema,
    )
    from infrastructure.persistence.storyos.schemas.conflict_schema import (
        ConflictSchema,
    )
    from infrastructure.persistence.storyos.schemas.expectation_schema import (
        ExpectationSchema,
    )
    from infrastructure.persistence.storyos.schemas.foreshadowing_schema import (
        ForeshadowingSchema,
    )
    from infrastructure.persistence.storyos.schemas.goal_schema import GoalSchema
    from infrastructure.persistence.storyos.schemas.mystery_schema import (
        MysterySchema,
    )
    from infrastructure.persistence.storyos.schemas.promise_schema import (
        PromiseSchema,
    )
    from infrastructure.persistence.storyos.schemas.reveal_schema import (
        RevealSchema,
    )
    from infrastructure.persistence.storyos.schemas.sflog_event_schema import (
        SFLogEventSchema,
    )
    from infrastructure.persistence.storyos.schemas.twist_schema import TwistSchema

    pairs = [
        # 8 registry tables (BaseRegistrySchema + entity fields)
        ("storyos_conflict_v1", ConflictSchema),
        ("storyos_mystery_v1", MysterySchema),
        ("storyos_twist_v1", TwistSchema),
        ("storyos_promise_v1", PromiseSchema),
        ("storyos_reveal_v1", RevealSchema),
        ("storyos_expectation_v1", ExpectationSchema),
        ("storyos_goal_v1", GoalSchema),
        ("storyos_foreshadowing_v1", ForeshadowingSchema),
        # 3 audit tables
        ("storyos_cascade_history_v1", CascadeHistorySchema),
        ("storyos_sflog_event_v1", SFLogEventSchema),
        ("storyos_bridge_log_v1", BridgeLogSchema),
    ]
    conn = sqlite3.connect(str(db_path))
    try:
        storyos_init_0001.upgrade(conn)
        for table_name, schema_cls in pairs:
            cur = conn.execute(f"PRAGMA table_info({table_name})")
            ddl_cols = {row[1] for row in cur.fetchall()}
            sa_cols = {c.name for c in schema_cls.__table__.columns}
            assert ddl_cols == sa_cols, (
                f"{table_name}: DDL has extra={ddl_cols - sa_cols}, "
                f"missing={sa_cols - ddl_cols}"
            )
    finally:
        conn.close()