"""storyos_migration_log_v1 表 ORM 定义。

schema（spec §1E 锁定）：
    id TEXT PRIMARY KEY
    project_id TEXT NOT NULL
    migration_type TEXT NOT NULL         -- 'foreshadowing_v1'
    batch_id TEXT NOT NULL
    old_ids TEXT NOT NULL                -- JSON list
    status TEXT NOT NULL                 -- 'committed' | 'failed' | 'rolled_back'
    started_at TEXT NOT NULL
    completed_at TEXT
    error TEXT
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class MigrationLogSchema:
    """storyos_migration_log_v1 行数据。"""
    id: str
    project_id: str
    migration_type: str
    batch_id: str
    old_ids_json: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS storyos_migration_log_v1 (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    migration_type TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    old_ids TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_migration_log_project_type
    ON storyos_migration_log_v1(project_id, migration_type, status);
"""