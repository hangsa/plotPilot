"""Mystery schema — storyos_mystery_v1."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.storyos.schemas.base import Base, BaseRegistrySchema


class MysterySchema(BaseRegistrySchema, Base):
    __tablename__ = "storyos_mystery_v1"

    clues: Mapped[list] = mapped_column(JSON, default=list)
    related_mystery: Mapped[Optional[str]] = mapped_column(String, nullable=True)