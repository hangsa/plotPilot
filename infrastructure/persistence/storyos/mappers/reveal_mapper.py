"""Reveal mapper — entity ↔ ORM row.

The entity's main text field is `content`; the BaseRegistrySchema mixin
provides a `description` column, so this mapper translates between the two
names on both directions.
"""
from __future__ import annotations

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.reveal import Reveal
from infrastructure.persistence.storyos.schemas.reveal_schema import RevealSchema


class RevealMapper:
    @staticmethod
    def to_orm(r: Reveal) -> RevealSchema:
        return RevealSchema(
            id=r.id,
            project_id=r.novel_id,
            created_chapter=0,
            status=r.status.value,
            description=r.content,
            linked_assets={},
            related_mystery=r.related_mystery,
            linked_to_conflict=r.linked_to_conflict,
            revealed_in_chapter=r.revealed_in_chapter,
        )

    @staticmethod
    def to_domain(row: RevealSchema) -> Reveal:
        return Reveal(
            id=row.id,
            novel_id=row.project_id,
            content=row.description,
            status=AssetStatus(row.status),
            related_mystery=row.related_mystery,
            linked_to_conflict=row.linked_to_conflict,
            revealed_in_chapter=row.revealed_in_chapter,
        )