"""Goal mapper — entity ↔ ORM row.

ProgressMarker (IntEnum T0..T9) round-trips via its `.value` int.
"""
from __future__ import annotations

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.goal import Goal, ProgressMarker
from infrastructure.persistence.storyos.schemas.goal_schema import GoalSchema


class GoalMapper:
    @staticmethod
    def to_orm(g: Goal) -> GoalSchema:
        return GoalSchema(
            id=g.id,
            project_id=g.novel_id,
            created_chapter=g.created_chapter,
            status=g.status.value,
            description=g.description,
            linked_assets={},
            current_progress=g.current_progress.value,
        )

    @staticmethod
    def to_domain(row: GoalSchema) -> Goal:
        return Goal(
            id=row.id,
            novel_id=row.project_id,
            description=row.description,
            status=AssetStatus(row.status),
            created_chapter=row.created_chapter,
            current_progress=ProgressMarker(row.current_progress),
        )