"""Expectation entity Pydantic DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.expectation import Expectation
from interfaces.api.v1.storyos.schemas.common_schemas import PaginationMeta


class ExpectationCreateRequest(BaseModel):
    """POST /expectations body."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=2000)
    created_chapter: int = Field(ge=1)
    status: AssetStatus = AssetStatus.ACTIVE
    intensity: int = Field(default=50, ge=0, le=100)


class ExpectationUpdateRequest(BaseModel):
    """PATCH /expectations/{id} body."""

    model_config = ConfigDict(extra="forbid")

    description: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: Optional[AssetStatus] = None
    intensity: Optional[int] = Field(default=None, ge=0, le=100)


class ExpectationResponse(BaseModel):
    """GET /expectations/{id} response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    intensity: int

    @classmethod
    def from_domain(cls, entity: Expectation) -> "ExpectationResponse":
        return cls(
            id=entity.id,
            project_id=entity.novel_id,
            description=entity.description,
            status=entity.status,
            created_chapter=entity.created_chapter,
            intensity=entity.intensity,
        )


class ExpectationListResponse(BaseModel):
    """GET /expectations list response."""

    model_config = ConfigDict(extra="forbid")
    data: list[ExpectationResponse]
    meta: PaginationMeta