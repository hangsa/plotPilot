"""MigrationAuditService —— 进程内审计聚合。

注：审计记录保存在内存（不持久化），CLI / API 进程退出后丢失。
长期审计通过 migration_log 表（spec §1E）持久化。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass(frozen=True)
class MigrationAuditRecord:
    migration_id: str
    project_id: str
    batches_total: int
    batches_done: int
    records_migrated: int
    duration_ms: int
    status: str
    errors: List[str]
    started_at: str


class MigrationAuditService:
    def __init__(self) -> None:
        self._records: Dict[str, MigrationAuditRecord] = {}

    def record_migration(
        self,
        migration_id: str,
        project_id: str,
        batches_total: int,
        batches_done: int,
        records_migrated: int,
        errors: List[str],
        duration_ms: Optional[int] = None,
    ) -> None:
        if batches_done == batches_total:
            status = "completed"
        elif batches_done == 0:
            status = "failed"
        else:
            status = "partial"

        self._records[migration_id] = MigrationAuditRecord(
            migration_id=migration_id,
            project_id=project_id,
            batches_total=batches_total,
            batches_done=batches_done,
            records_migrated=records_migrated,
            duration_ms=duration_ms or 0,
            status=status,
            errors=list(errors),
            started_at=datetime.utcnow().isoformat(),
        )

    def get_record(self, migration_id: str) -> Optional[MigrationAuditRecord]:
        return self._records.get(migration_id)

    def all_records(self) -> List[MigrationAuditRecord]:
        return list(self._records.values())