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

    def aggregate_report(self) -> dict:
        """聚合所有审计记录生成最终 JSON 报告（CLI --status 输出）。"""
        records = self.all_records()
        by_project: Dict[str, Dict[str, int]] = {}
        total_errors = 0
        for r in records:
            by_project.setdefault(r.project_id, {"migrations": 0, "records": 0})
            by_project[r.project_id]["migrations"] += 1
            by_project[r.project_id]["records"] += r.records_migrated
            total_errors += len(r.errors)

        return {
            "total_migrations": len(records),
            "total_records_migrated": sum(r.records_migrated for r in records),
            "total_errors": total_errors,
            "by_project": by_project,
            "migrations": [
                {
                    "migration_id": r.migration_id,
                    "project_id": r.project_id,
                    "batches_total": r.batches_total,
                    "batches_done": r.batches_done,
                    "records_migrated": r.records_migrated,
                    "status": r.status,
                    "errors": r.errors,
                    "started_at": r.started_at,
                }
                for r in records
            ],
        }