"""Cascade history schema — storyos_cascade_history_v1.

Append-only audit table: one row per CascadeStep attempt (executed OR blocked).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.storyos.schemas.base import Base, BaseRegistrySchema


class CascadeHistorySchema(BaseRegistrySchema, Base):
    __tablename__ = "storyos_cascade_history_v1"

    chapter_id: Mapped[int] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(String)
    source_asset_type: Mapped[str] = mapped_column(String)
    source_asset_id: Mapped[str] = mapped_column(String, index=True)
    target_asset_type: Mapped[str] = mapped_column(String)
    target_asset_id: Mapped[str] = mapped_column(String, index=True)
    executed: Mapped[bool] = mapped_column(Boolean)
    blocked_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )