"""Foreshadowing schema — storyos_foreshadowing_v1."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.storyos.schemas.base import Base, BaseRegistrySchema


class ForeshadowingSchema(BaseRegistrySchema, Base):
    __tablename__ = "storyos_foreshadowing_v1"

    importance: Mapped[str] = mapped_column(String)
    planted_in_chapter: Mapped[int] = mapped_column(Integer)
    suggested_resolve_chapter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolved_in_chapter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    migrated_from_legacy_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )