"""Promise mapper — entity ↔ ORM row."""
from __future__ import annotations

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.promise import Promise
from infrastructure.persistence.storyos.schemas.promise_schema import PromiseSchema


class PromiseMapper:
    @staticmethod
    def to_orm(p: Promise) -> PromiseSchema:
        return PromiseSchema(
            id=p.id,
            project_id=p.novel_id,
            created_chapter=p.made_in_chapter,
            status=p.status.value,
            description=p.description,
            linked_assets={},
            made_in_chapter=p.made_in_chapter,
            importance=p.importance,
            fulfilled_in_chapter=p.fulfilled_in_chapter,
        )

    @staticmethod
    def to_domain(row: PromiseSchema) -> Promise:
        return Promise(
            id=row.id,
            novel_id=row.project_id,
            description=row.description,
            made_in_chapter=row.made_in_chapter,
            status=AssetStatus(row.status),
            importance=row.importance,
            fulfilled_in_chapter=row.fulfilled_in_chapter,
        )