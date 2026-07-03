"""Promise schema — storyos_promise_v1."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.storyos.schemas.base import Base, BaseRegistrySchema


class PromiseSchema(BaseRegistrySchema, Base):
    __tablename__ = "storyos_promise_v1"

    made_in_chapter: Mapped[int] = mapped_column(Integer)
    importance: Mapped[int] = mapped_column(Integer)
    fulfilled_in_chapter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)