"""Bridge log schema — storyos_bridge_log_v1. ⚡ CRITICAL AUDIT TABLE.

This is THE post-mortem audit table for the WriteDispatch.transaction() bridge.
It is intentionally written OUTSIDE the bridge transaction so that even when the
transaction ROLLBACKs, the failure metadata survives for forensic analysis.

Per CONVENTIONS.md: this table is the documented audit-only exception that does
NOT inherit BaseRegistrySchema — it has its own compact 12-column layout with
no shared registry fields. The 9 mixin columns (status / description /
linked_assets / cascade_updated_at / created_chapter) are not meaningful for
a write-once audit record.

Append-only. Never updated. Never deleted (except via full migration).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.persistence.storyos.schemas.base import Base


class BridgeLogSchema(Base):
    __tablename__ = "storyos_bridge_log_v1"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    chapter_id: Mapped[int] = mapped_column(Integer, index=True)
    transaction_id: Mapped[str] = mapped_column(String)
    evolution_actions_count: Mapped[int] = mapped_column(Integer)
    registry_updates_count: Mapped[int] = mapped_column(Integer)
    cascade_steps_count: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )