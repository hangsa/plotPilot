"""migration_log 仓储（断点续跑 + 审计持久化）。"""
from __future__ import annotations

import json
from typing import Any, Callable, List, Optional, Set

from infrastructure.persistence.storyos.migration_log_mapper import (
    MigrationLogEntry,
    MigrationLogMapper,
    MigrationStatus,
)

DbProvider = Callable[[], Any]


class MigrationLogRepository:
    """storyos_migration_log_v1 表 CRUD 仓储。"""

    def __init__(self, db_provider: DbProvider) -> None:
        self._db_provider = db_provider

    def record_committed_batch(
        self,
        migration_id: str,
        project_id: str,
        batch_id: str,
        old_ids: List[str],
        started_at: str,
        completed_at: str,
    ) -> None:
        self._insert_log(
            migration_id=migration_id,
            project_id=project_id,
            batch_id=batch_id,
            old_ids=old_ids,
            status=MigrationStatus.COMMITTED,
            started_at=started_at,
            completed_at=completed_at,
            error=None,
        )

    def record_failed_batch(
        self,
        migration_id: str,
        project_id: str,
        batch_id: str,
        old_ids: List[str],
        started_at: str,
        error: str,
    ) -> None:
        self._insert_log(
            migration_id=migration_id,
            project_id=project_id,
            batch_id=batch_id,
            old_ids=old_ids,
            status=MigrationStatus.FAILED,
            started_at=started_at,
            completed_at=None,
            error=error,
        )

    def _insert_log(
        self,
        migration_id: str,
        project_id: str,
        batch_id: str,
        old_ids: List[str],
        status: MigrationStatus,
        started_at: str,
        completed_at: Optional[str],
        error: Optional[str],
    ) -> None:
        db = self._db_provider()
        db.execute(
            "INSERT INTO storyos_migration_log_v1 "
            "(id, project_id, migration_type, batch_id, old_ids, status, started_at, completed_at, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                migration_id,
                project_id,
                "foreshadowing_v1",
                batch_id,
                json.dumps(old_ids),
                status.value,
                started_at,
                completed_at,
                error,
            ),
        )
        db.commit()

    def get_committed_old_ids(
        self,
        project_id: str,
        migration_type: str = "foreshadowing_v1",
    ) -> Set[str]:
        """返回该项目+类型下所有已 committed 的 old_id 集合（供断点续跑过滤）。"""
        db = self._db_provider()
        rows = db.execute(
            "SELECT DISTINCT json_each.value FROM storyos_migration_log_v1, "
            "json_each(storyos_migration_log_v1.old_ids) "
            "WHERE project_id = ? AND migration_type = ? AND status = 'committed'",
            (project_id, migration_type),
        ).fetchall()
        return {row[0] for row in rows}

    def mark_rolled_back(self, migration_id: str) -> None:
        """把单条 committed → rolled_back（rollback 流程）。"""
        db = self._db_provider()
        db.execute(
            "UPDATE storyos_migration_log_v1 SET status = 'rolled_back' "
            "WHERE id = ? AND status = 'committed'",
            (migration_id,),
        )
        db.commit()

    def get_entry(self, migration_id: str) -> Optional[MigrationLogEntry]:
        db = self._db_provider()
        row = db.execute(
            "SELECT id, project_id, migration_type, batch_id, old_ids, status, "
            "started_at, completed_at, error FROM storyos_migration_log_v1 WHERE id = ?",
            (migration_id,),
        ).fetchone()
        if row is None:
            return None
        return MigrationLogMapper.row_to_entry(row)