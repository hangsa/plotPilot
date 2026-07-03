"""Reveal schema — storyos_reveal_v1."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.storyos.schemas.base import Base, BaseRegistrySchema


class RevealSchema(BaseRegistrySchema, Base):
    __tablename__ = "storyos_reveal_v1"

    related_mystery: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    linked_to_conflict: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    revealed_in_chapter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)