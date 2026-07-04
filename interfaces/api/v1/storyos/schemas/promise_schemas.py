"""Promise entity Pydantic DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.promise import Promise
from interfaces.api.v1.storyos.schemas.common_schemas import PaginationMeta


class PromiseCreateRequest(BaseModel):
    """POST /promises body."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=2000)
    made_in_chapter: int = Field(ge=1)
    status: AssetStatus = AssetStatus.ACTIVE
    importance: int = Field(default=50, ge=0, le=100)
    fulfilled_in_chapter: Optional[int] = Field(default=None, ge=1)


class PromiseUpdateRequest(BaseModel):
    """PATCH /promises/{id} body."""

    model_config = ConfigDict(extra="forbid")

    description: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: Optional[AssetStatus] = None
    importance: Optional[int] = Field(default=None, ge=0, le=100)
    fulfilled_in_chapter: Optional[int] = Field(default=None, ge=1)


class PromiseResponse(BaseModel):
    """GET /promises/{id} response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    description: str
    status: AssetStatus
    made_in_chapter: int
    importance: int
    fulfilled_in_chapter: Optional[int] = None

    @classmethod
    def from_domain(cls, entity: Promise) -> "PromiseResponse":
        return cls(
            id=entity.id,
            project_id=entity.novel_id,
            description=entity.description,
            status=entity.status,
            made_in_chapter=entity.made_in_chapter,
            importance=entity.importance,
            fulfilled_in_chapter=entity.fulfilled_in_chapter,
        )


class PromiseListResponse(BaseModel):
    """GET /promises list response."""

    model_config = ConfigDict(extra="forbid")
    data: list[PromiseResponse]
    meta: PaginationMeta