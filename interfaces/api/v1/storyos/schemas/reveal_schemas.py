"""Reveal entity Pydantic DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.reveal import Reveal
from interfaces.api.v1.storyos.schemas.common_schemas import PaginationMeta


class RevealCreateRequest(BaseModel):
    """POST /reveals body."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=2000)
    status: AssetStatus = AssetStatus.HIDDEN
    related_mystery: Optional[str] = None
    linked_to_conflict: Optional[str] = None
    revealed_in_chapter: Optional[int] = Field(default=None, ge=1)


class RevealUpdateRequest(BaseModel):
    """PATCH /reveals/{id} body."""

    model_config = ConfigDict(extra="forbid")

    content: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: Optional[AssetStatus] = None
    related_mystery: Optional[str] = None
    linked_to_conflict: Optional[str] = None
    revealed_in_chapter: Optional[int] = Field(default=None, ge=1)


class RevealResponse(BaseModel):
    """GET /reveals/{id} response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    content: str
    status: AssetStatus
    related_mystery: Optional[str] = None
    linked_to_conflict: Optional[str] = None
    revealed_in_chapter: Optional[int] = None

    @classmethod
    def from_domain(cls, entity: Reveal) -> "RevealResponse":
        return cls(
            id=entity.id,
            project_id=entity.novel_id,
            content=entity.content,
            status=entity.status,
            related_mystery=entity.related_mystery,
            linked_to_conflict=entity.linked_to_conflict,
            revealed_in_chapter=entity.revealed_in_chapter,
        )


class RevealListResponse(BaseModel):
    """GET /reveals list response."""

    model_config = ConfigDict(extra="forbid")
    data: list[RevealResponse]
    meta: PaginationMeta