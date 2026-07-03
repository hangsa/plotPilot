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