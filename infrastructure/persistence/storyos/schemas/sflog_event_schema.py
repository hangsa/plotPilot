"""SFLog event schema — storyos_sflog_event_v1.

Append-only audit table: one row per SF_LOG line extracted from chapter text.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.storyos.schemas.base import Base, BaseRegistrySchema


class SFLogEventSchema(BaseRegistrySchema, Base):
    __tablename__ = "storyos_sflog_event_v1"

    chapter_id: Mapped[int] = mapped_column(Integer, index=True)
    raw_text: Mapped[str] = mapped_column(String)
    log_type: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)
    params: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)