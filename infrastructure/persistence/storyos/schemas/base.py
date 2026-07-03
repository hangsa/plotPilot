"""BaseRegistrySchema — 11 张表共用的 mixin 字段。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Concrete declarative base for all StoryOS schemas.

    Subclasses must combine BaseRegistrySchema + Base to get both the shared
    fields and the declarative machinery.
    """


class BaseRegistrySchema:
    """8 registry 表的共用 mixin（spec §3.4 锁定 9 字段）。

    字段：
        id: 业务主键（str）
        project_id: FK 到 novels
        created_chapter: 创建章节
        status: AssetStatus.value
        description: 描述
        linked_assets: JSON dict[str, str]
        cascade_updated_at: 最近一次级联更新时间
        created_at / updated_at: UTC 时间戳
    """

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    created_chapter: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    linked_assets: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cascade_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )