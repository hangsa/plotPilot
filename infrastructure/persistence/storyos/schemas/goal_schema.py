"""Goal schema — storyos_goal_v1."""
from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.storyos.schemas.base import Base, BaseRegistrySchema


class GoalSchema(BaseRegistrySchema, Base):
    __tablename__ = "storyos_goal_v1"

    current_progress: Mapped[int] = mapped_column(Integer)