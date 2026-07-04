"""row ↔ MigrationLogEntry 映射。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class MigrationStatus(str, Enum):
    COMMITTED = "committed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class MigrationLogEntry:
    id: str
    project_id: str
    migration_type: str
    batch_id: str
    old_ids: List[str]
    status: MigrationStatus
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class MigrationLogMapper:
    @staticmethod
    def row_to_entry(row: tuple) -> MigrationLogEntry:
        return MigrationLogEntry(
            id=row[0],
            project_id=row[1],
            migration_type=row[2],
            batch_id=row[3],
            old_ids=json.loads(row[4]) if row[4] else [],
            status=MigrationStatus(row[5]),
            started_at=row[6],
            completed_at=row[7],
            error=row[8],
        )

    @staticmethod
    def entry_to_row(entry: MigrationLogEntry) -> tuple:
        return (
            entry.id,
            entry.project_id,
            entry.migration_type,
            entry.batch_id,
            json.dumps(entry.old_ids),
            entry.status.value,
            entry.started_at,
            entry.completed_at,
            entry.error,
        )