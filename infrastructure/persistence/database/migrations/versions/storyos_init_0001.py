"""Alembic 迁移: 0001_storyos_init — 创建 12 张 storyos 表。

Phase 1A 直调约定 (E3 / F1):
    本模块暴露 ``upgrade(conn)`` 与 ``downgrade(conn)`` 两个普通可调用对象,
    接受一个 :class:`sqlite3.Connection`. 1A 阶段的测试与运维脚本直接调用
    这两个函数, 不依赖完整的 alembic env 配置 (env setup 在 Phase 1E 补完).

DDL 约定:
    - 所有 DDL 均使用 ``CREATE TABLE IF NOT EXISTS`` / ``CREATE INDEX IF NOT EXISTS``,
      保证 ``upgrade()`` 重复调用安全 (幂等)。
    - 表/索引标识符均为模块内硬编码常量, 不接受任何外部输入 — 直接字符串拼接。
    - 每个 ``_create_*`` 函数在末尾调用 ``conn.commit()``, 确保表在函数返回前已落盘。
"""
from __future__ import annotations

import sqlite3

from infrastructure.persistence.storyos import migration_log_schema

# ---------------------------------------------------------------------------
# 表清单 (12 张) — 模块级常量, 供 upgrade / downgrade 共用
# ---------------------------------------------------------------------------

_REGISTRY_TABLES: tuple[str, ...] = (
    "storyos_conflict_v1",
    "storyos_mystery_v1",
    "storyos_twist_v1",
    "storyos_promise_v1",
    "storyos_reveal_v1",
    "storyos_expectation_v1",
    "storyos_goal_v1",
    "storyos_foreshadowing_v1",
)

_AUDIT_TABLES: tuple[str, ...] = (
    "storyos_cascade_history_v1",
    "storyos_sflog_event_v1",
    "storyos_bridge_log_v1",
)

_MIGRATION_TABLES: tuple[str, ...] = (
    "storyos_migration_log_v1",
)

ALL_TABLES: tuple[str, ...] = _REGISTRY_TABLES + _AUDIT_TABLES + _MIGRATION_TABLES


# ---------------------------------------------------------------------------
# 公共入口
# ---------------------------------------------------------------------------


def upgrade(conn: sqlite3.Connection) -> None:
    """创建全部 12 张 storyos 表 + 索引。"""
    _create_conflict(conn)
    _create_mystery(conn)
    _create_twist(conn)
    _create_promise(conn)
    _create_reveal(conn)
    _create_expectation(conn)
    _create_goal(conn)
    _create_foreshadowing(conn)
    _create_cascade_history(conn)
    _create_sflog_event(conn)
    _create_bridge_log(conn)
    _create_migration_log(conn)


def downgrade(conn: sqlite3.Connection) -> None:
    """删除全部 12 张 storyos 表 (顺序无关)。"""
    for table in ALL_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()


# ---------------------------------------------------------------------------
# 8 张 registry 表 (BaseRegistrySchema 9 字段 + 实体专属字段)
# ---------------------------------------------------------------------------


def _create_conflict(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storyos_conflict_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_chapter INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            linked_assets TEXT NOT NULL DEFAULT '{}',
            cascade_updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            intensity TEXT NOT NULL,
            involved_characters TEXT NOT NULL DEFAULT '[]',
            linked_conflicts TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_conflict_v1_project_id "
        "ON storyos_conflict_v1(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_conflict_v1_status "
        "ON storyos_conflict_v1(status)"
    )
    conn.commit()


def _create_mystery(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storyos_mystery_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_chapter INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            linked_assets TEXT NOT NULL DEFAULT '{}',
            cascade_updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            clues TEXT NOT NULL DEFAULT '[]',
            related_mystery TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_mystery_v1_project_id "
        "ON storyos_mystery_v1(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_mystery_v1_status "
        "ON storyos_mystery_v1(status)"
    )
    conn.commit()


def _create_twist(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storyos_twist_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_chapter INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            linked_assets TEXT NOT NULL DEFAULT '{}',
            cascade_updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            twist_type TEXT NOT NULL,
            reveal_trigger TEXT,
            forbidden_concurrent TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_twist_v1_project_id "
        "ON storyos_twist_v1(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_twist_v1_status "
        "ON storyos_twist_v1(status)"
    )
    conn.commit()


def _create_promise(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storyos_promise_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_chapter INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            linked_assets TEXT NOT NULL DEFAULT '{}',
            cascade_updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            made_in_chapter INTEGER NOT NULL,
            importance INTEGER NOT NULL CHECK (importance BETWEEN 0 AND 100),
            fulfilled_in_chapter INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_promise_v1_project_id "
        "ON storyos_promise_v1(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_promise_v1_status "
        "ON storyos_promise_v1(status)"
    )
    conn.commit()


def _create_reveal(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storyos_reveal_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_chapter INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            linked_assets TEXT NOT NULL DEFAULT '{}',
            cascade_updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            related_mystery TEXT NOT NULL,
            linked_to_conflict TEXT,
            revealed_in_chapter INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_reveal_v1_project_id "
        "ON storyos_reveal_v1(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_reveal_v1_status "
        "ON storyos_reveal_v1(status)"
    )
    conn.commit()


def _create_expectation(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storyos_expectation_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_chapter INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            linked_assets TEXT NOT NULL DEFAULT '{}',
            cascade_updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            intensity INTEGER NOT NULL CHECK (intensity BETWEEN 0 AND 100)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_expectation_v1_project_id "
        "ON storyos_expectation_v1(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_expectation_v1_status "
        "ON storyos_expectation_v1(status)"
    )
    conn.commit()


def _create_goal(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storyos_goal_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_chapter INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            linked_assets TEXT NOT NULL DEFAULT '{}',
            cascade_updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            current_progress INTEGER NOT NULL CHECK (current_progress BETWEEN 0 AND 9)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_goal_v1_project_id "
        "ON storyos_goal_v1(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_goal_v1_status "
        "ON storyos_goal_v1(status)"
    )
    conn.commit()


def _create_foreshadowing(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storyos_foreshadowing_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_chapter INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            linked_assets TEXT NOT NULL DEFAULT '{}',
            cascade_updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            importance TEXT NOT NULL,
            planted_in_chapter INTEGER NOT NULL,
            suggested_resolve_chapter INTEGER,
            resolved_in_chapter INTEGER
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_foreshadowing_v1_project_id "
        "ON storyos_foreshadowing_v1(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_foreshadowing_v1_status "
        "ON storyos_foreshadowing_v1(status)"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 3 张 audit 表
# ---------------------------------------------------------------------------


def _create_cascade_history(conn: sqlite3.Connection) -> None:
    """cascade_history: 9 mixin 字段 + 8 实体列。索引 4 个 (project_id, status, source_asset_id, target_asset_id)。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storyos_cascade_history_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_chapter INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            linked_assets TEXT NOT NULL DEFAULT '{}',
            cascade_updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            chapter_id INTEGER NOT NULL,
            trigger TEXT NOT NULL,
            source_asset_type TEXT NOT NULL,
            source_asset_id TEXT NOT NULL,
            target_asset_type TEXT NOT NULL,
            target_asset_id TEXT NOT NULL,
            executed INTEGER NOT NULL,
            blocked_reason TEXT,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_cascade_history_v1_project_id "
        "ON storyos_cascade_history_v1(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_cascade_history_v1_status "
        "ON storyos_cascade_history_v1(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_cascade_history_v1_source_asset_id "
        "ON storyos_cascade_history_v1(source_asset_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_cascade_history_v1_target_asset_id "
        "ON storyos_cascade_history_v1(target_asset_id)"
    )
    conn.commit()


def _create_sflog_event(conn: sqlite3.Connection) -> None:
    """sflog_event: 9 mixin 字段 + 6 实体列 (status 列复用 mixin)。索引 4 个 (project_id, status, chapter_id, log_type)。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storyos_sflog_event_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_chapter INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            linked_assets TEXT NOT NULL DEFAULT '{}',
            cascade_updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            chapter_id INTEGER NOT NULL,
            raw_text TEXT NOT NULL,
            log_type TEXT NOT NULL,
            params TEXT NOT NULL DEFAULT '{}',
            error TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_sflog_event_v1_project_id "
        "ON storyos_sflog_event_v1(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_sflog_event_v1_status "
        "ON storyos_sflog_event_v1(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_sflog_event_v1_chapter_id "
        "ON storyos_sflog_event_v1(chapter_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_sflog_event_v1_log_type "
        "ON storyos_sflog_event_v1(log_type)"
    )
    conn.commit()


def _create_bridge_log(conn: sqlite3.Connection) -> None:
    """⚡ bridge_log: 不混入 BaseRegistrySchema, 自包含 11 列。索引 2 个 (project_id, chapter_id)。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS storyos_bridge_log_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            chapter_id INTEGER NOT NULL,
            transaction_id TEXT NOT NULL,
            evolution_actions_count INTEGER NOT NULL,
            registry_updates_count INTEGER NOT NULL,
            cascade_steps_count INTEGER NOT NULL,
            success INTEGER NOT NULL,
            error TEXT,
            duration_ms INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_bridge_log_v1_project_id "
        "ON storyos_bridge_log_v1(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_storyos_bridge_log_v1_chapter_id "
        "ON storyos_bridge_log_v1(chapter_id)"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 1 张 migration 表
# ---------------------------------------------------------------------------


def _create_migration_log(conn: sqlite3.Connection) -> None:
    """migration_log: 9 列 (id, project_id, migration_type, batch_id, old_ids, status, started_at, completed_at, error)。
    DDL 委托给 ``migration_log_schema.CREATE_TABLE_SQL`` (含表 CREATE + 复合索引
    ``idx_migration_log_project_type``)。供 ``MigrationLogRepository`` 在生产 migration
    断点续跑 + 审计持久化中使用。"""
    conn.executescript(migration_log_schema.CREATE_TABLE_SQL)
    conn.commit()
