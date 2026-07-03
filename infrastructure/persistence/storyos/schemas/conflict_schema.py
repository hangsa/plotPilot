"""Conflict schema — storyos_conflict_v1."""
from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.storyos.schemas.base import Base, BaseRegistrySchema


class ConflictSchema(BaseRegistrySchema, Base):
    __tablename__ = "storyos_conflict_v1"

    intensity: Mapped[str] = mapped_column(String)
    involved_characters: Mapped[list[str]] = mapped_column(JSON, default=list)
    linked_conflicts: Mapped[list[str]] = mapped_column(JSON, default=list)