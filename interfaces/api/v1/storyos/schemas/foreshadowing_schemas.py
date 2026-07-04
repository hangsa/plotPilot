"""Foreshadowing entity Pydantic DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus
from domain.novel.value_objects.foreshadowing import ImportanceLevel
from domain.storyos.entities.foreshadowing import Foreshadowing


class ForeshadowingCreateRequest(BaseModel):
    """POST /foreshadowings body."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=2000)
    planted_in_chapter: int = Field(ge=1)
    status: AssetStatus = AssetStatus.PLANTED
    importance: ImportanceLevel = ImportanceLevel.MEDIUM
    suggested_resolve_chapter: Optional[int] = Field(default=None, ge=1)
    resolved_in_chapter: Optional[int] = Field(default=None, ge=1)


class ForeshadowingUpdateRequest(BaseModel):
    """PATCH /foreshadowings/{id} body."""

    model_config = ConfigDict(extra="forbid")

    description: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: Optional[AssetStatus] = None
    importance: Optional[ImportanceLevel] = None
    suggested_resolve_chapter: Optional[int] = Field(default=None, ge=1)
    resolved_in_chapter: Optional[int] = Field(default=None, ge=1)


class ForeshadowingResponse(BaseModel):
    """GET /foreshadowings/{id} response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    description: str
    status: AssetStatus
    importance: ImportanceLevel
    planted_in_chapter: int
    suggested_resolve_chapter: Optional[int] = None
    resolved_in_chapter: Optional[int] = None

    @classmethod
    def from_domain(cls, entity: Foreshadowing) -> "ForeshadowingResponse":
        return cls(
            id=entity.id,
            project_id=entity.novel_id,
            description=entity.description,
            status=entity.status,
            importance=entity.importance,
            planted_in_chapter=entity.planted_in_chapter,
            suggested_resolve_chapter=entity.suggested_resolve_chapter,
            resolved_in_chapter=entity.resolved_in_chapter,
        )