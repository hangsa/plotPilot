"""Twist schema — storyos_twist_v1."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.storyos.schemas.base import Base, BaseRegistrySchema


class TwistSchema(BaseRegistrySchema, Base):
    __tablename__ = "storyos_twist_v1"

    twist_type: Mapped[str] = mapped_column(String)
    reveal_trigger: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    forbidden_concurrent: Mapped[list[str]] = mapped_column(JSON, default=list)