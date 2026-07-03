"""SFLogEvent mapper — audit record ↔ ORM row.

`SFLogEventEntry` is a frozen dataclass that mirrors one row of
`storyos_sflog_event_v1` (append-only audit). Each entry corresponds to one
SF_LOG line extracted from chapter text, with its parse/apply status.

The mapper bridges to BaseRegistrySchema's `created_chapter` column by using
the entry's `chapter_id` (per plan §E3 option (b)).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from infrastructure.persistence.storyos.schemas.sflog_event_schema import (
    SFLogEventSchema,
)


@dataclass(frozen=True)
class SFLogEventEntry:
    id: str
    project_id: str
    chapter_id: int
    raw_text: str
    log_type: str
    status: str
    params: dict[str, str]
    error: Optional[str]


class SFLogEventMapper:
    @staticmethod
    def to_orm(entry: SFLogEventEntry) -> SFLogEventSchema:
        return SFLogEventSchema(
            id=entry.id,
            project_id=entry.project_id,
            created_chapter=entry.chapter_id,
            status=entry.status,
            description=entry.raw_text,
            linked_assets={},
            chapter_id=entry.chapter_id,
            raw_text=entry.raw_text,
            log_type=entry.log_type,
            params=dict(entry.params),
            error=entry.error,
        )

    @staticmethod
    def to_domain(row: SFLogEventSchema) -> SFLogEventEntry:
        return SFLogEventEntry(
            id=row.id,
            project_id=row.project_id,
            chapter_id=row.chapter_id,
            raw_text=row.raw_text,
            log_type=row.log_type,
            status=row.status,
            params=dict(row.params or {}),
            error=row.error,
        )