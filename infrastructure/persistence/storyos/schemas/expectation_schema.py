"""Expectation schema — storyos_expectation_v1."""
from __future__ import annotations

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.storyos.schemas.base import Base, BaseRegistrySchema


class ExpectationSchema(BaseRegistrySchema, Base):
    __tablename__ = "storyos_expectation_v1"

    intensity: Mapped[int] = mapped_column(Integer)