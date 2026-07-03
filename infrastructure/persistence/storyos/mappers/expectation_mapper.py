"""Expectation mapper — entity ↔ ORM row."""
from __future__ import annotations

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.expectation import Expectation
from infrastructure.persistence.storyos.schemas.expectation_schema import (
    ExpectationSchema,
)


class ExpectationMapper:
    @staticmethod
    def to_orm(e: Expectation) -> ExpectationSchema:
        return ExpectationSchema(
            id=e.id,
            project_id=e.novel_id,
            created_chapter=e.created_chapter,
            status=e.status.value,
            description=e.description,
            linked_assets={},
            intensity=e.intensity,
        )

    @staticmethod
    def to_domain(row: ExpectationSchema) -> Expectation:
        return Expectation(
            id=row.id,
            novel_id=row.project_id,
            description=row.description,
            status=AssetStatus(row.status),
            created_chapter=row.created_chapter,
            intensity=row.intensity,
        )