"""BridgeLog mapper — audit record ↔ ORM row. ⚡ CRITICAL.

`BridgeLogEntry` is a frozen dataclass that mirrors one row of
`storyos_bridge_log_v1`. This is the post-mortem audit table: written OUTSIDE
the WriteDispatch transaction so that even on ROLLBACK the failure metadata
survives. There is no business logic here — the mapper is purely structural.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from infrastructure.persistence.storyos.schemas.bridge_log_schema import (
    BridgeLogSchema,
)


@dataclass(frozen=True)
class BridgeLogEntry:
    id: str
    project_id: str
    chapter_id: int
    transaction_id: str
    evolution_actions_count: int
    registry_updates_count: int
    cascade_steps_count: int
    success: bool
    error: Optional[str]
    duration_ms: int


class BridgeLogMapper:
    @staticmethod
    def to_orm(entry: BridgeLogEntry) -> BridgeLogSchema:
        return BridgeLogSchema(
            id=entry.id,
            project_id=entry.project_id,
            chapter_id=entry.chapter_id,
            transaction_id=entry.transaction_id,
            evolution_actions_count=entry.evolution_actions_count,
            registry_updates_count=entry.registry_updates_count,
            cascade_steps_count=entry.cascade_steps_count,
            success=entry.success,
            error=entry.error,
            duration_ms=entry.duration_ms,
        )

    @staticmethod
    def to_domain(row: BridgeLogSchema) -> BridgeLogEntry:
        return BridgeLogEntry(
            id=row.id,
            project_id=row.project_id,
            chapter_id=row.chapter_id,
            transaction_id=row.transaction_id,
            evolution_actions_count=row.evolution_actions_count,
            registry_updates_count=row.registry_updates_count,
            cascade_steps_count=row.cascade_steps_count,
            success=row.success,
            error=row.error,
            duration_ms=row.duration_ms,
        )