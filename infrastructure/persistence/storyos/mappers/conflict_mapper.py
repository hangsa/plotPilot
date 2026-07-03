"""Conflict mapper — entity ↔ ORM row."""
from __future__ import annotations

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from infrastructure.persistence.storyos.schemas.conflict_schema import ConflictSchema


class ConflictMapper:
    @staticmethod
    def to_orm(c: Conflict) -> ConflictSchema:
        return ConflictSchema(
            id=c.id,
            project_id=c.novel_id,
            created_chapter=c.created_chapter,
            status=c.status.value,
            description=c.description,
            linked_assets={},
            intensity=c.intensity.name,
            involved_characters=list(c.involved_characters),
            linked_conflicts=list(c.linked_conflicts),
        )

    @staticmethod
    def to_domain(row: ConflictSchema) -> Conflict:
        return Conflict(
            id=row.id,
            novel_id=row.project_id,
            description=row.description,
            intensity=ConflictIntensity[row.intensity],
            status=AssetStatus(row.status),
            involved_characters=tuple(row.involved_characters or []),
            created_chapter=row.created_chapter,
            linked_conflicts=tuple(row.linked_conflicts or []),
        )