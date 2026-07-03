"""CascadeHistory mapper — audit record ↔ ORM row.

`CascadeHistoryEntry` is a frozen dataclass that mirrors one row of
`storyos_cascade_history_v1` (append-only audit). One entry per CascadeStep
attempt: `executed=True` means the step ran; `executed=False` means it was
blocked and `blocked_reason` is populated.

The mapper bridges to BaseRegistrySchema's `created_chapter` column by using
the entry's `chapter_id` (per plan §E3 option (b)).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from infrastructure.persistence.storyos.schemas.cascade_history_schema import (
    CascadeHistorySchema,
)


@dataclass(frozen=True)
class CascadeHistoryEntry:
    id: str
    project_id: str
    chapter_id: int
    trigger: str
    source_asset_type: str
    source_asset_id: str
    target_asset_type: str
    target_asset_id: str
    executed: bool
    blocked_reason: Optional[str]


class CascadeHistoryMapper:
    @staticmethod
    def to_orm(entry: CascadeHistoryEntry) -> CascadeHistorySchema:
        return CascadeHistorySchema(
            id=entry.id,
            project_id=entry.project_id,
            created_chapter=entry.chapter_id,
            status="executed" if entry.executed else "blocked",
            description=(
                f"{entry.trigger}: {entry.source_asset_type}"
                f":{entry.source_asset_id} -> {entry.target_asset_type}"
                f":{entry.target_asset_id}"
            ),
            linked_assets={},
            chapter_id=entry.chapter_id,
            trigger=entry.trigger,
            source_asset_type=entry.source_asset_type,
            source_asset_id=entry.source_asset_id,
            target_asset_type=entry.target_asset_type,
            target_asset_id=entry.target_asset_id,
            executed=entry.executed,
            blocked_reason=entry.blocked_reason,
        )

    @staticmethod
    def to_domain(row: CascadeHistorySchema) -> CascadeHistoryEntry:
        return CascadeHistoryEntry(
            id=row.id,
            project_id=row.project_id,
            chapter_id=row.chapter_id,
            trigger=row.trigger,
            source_asset_type=row.source_asset_type,
            source_asset_id=row.source_asset_id,
            target_asset_type=row.target_asset_type,
            target_asset_id=row.target_asset_id,
            executed=row.executed,
            blocked_reason=row.blocked_reason,
        )