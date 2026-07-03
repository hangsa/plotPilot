"""Twist mapper — entity ↔ ORM row.

The entity field `forbidden_concurrent_twists` is persisted under the column
name `forbidden_concurrent` (per test_first_batch_schemas.py assertion).
"""
from __future__ import annotations

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.twist import Twist, TwistType
from infrastructure.persistence.storyos.schemas.twist_schema import TwistSchema


class TwistMapper:
    @staticmethod
    def to_orm(t: Twist) -> TwistSchema:
        return TwistSchema(
            id=t.id,
            project_id=t.novel_id,
            created_chapter=t.created_chapter,
            status=t.status.value,
            description=t.description,
            linked_assets={},
            twist_type=t.twist_type.value,
            reveal_trigger=t.reveal_trigger,
            forbidden_concurrent=list(t.forbidden_concurrent_twists),
        )

    @staticmethod
    def to_domain(row: TwistSchema) -> Twist:
        return Twist(
            id=row.id,
            novel_id=row.project_id,
            description=row.description,
            status=AssetStatus(row.status),
            created_chapter=row.created_chapter,
            twist_type=TwistType(row.twist_type),
            reveal_trigger=row.reveal_trigger,
            forbidden_concurrent_twists=tuple(row.forbidden_concurrent or []),
        )