"""Twist entity Pydantic DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.twist import Twist, TwistType
from interfaces.api.v1.storyos.schemas.common_schemas import PaginationMeta


class TwistCreateRequest(BaseModel):
    """POST /twists body."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=2000)
    created_chapter: int = Field(ge=1)
    twist_type: TwistType
    status: AssetStatus = AssetStatus.ACTIVE
    reveal_trigger: Optional[str] = Field(default=None, max_length=500)
    forbidden_concurrent_twists: list[str] = Field(default_factory=list)


class TwistUpdateRequest(BaseModel):
    """PATCH /twists/{id} body."""

    model_config = ConfigDict(extra="forbid")

    description: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: Optional[AssetStatus] = None
    twist_type: Optional[TwistType] = None
    reveal_trigger: Optional[str] = Field(default=None, max_length=500)
    forbidden_concurrent_twists: Optional[list[str]] = None


class TwistResponse(BaseModel):
    """GET /twists/{id} response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    twist_type: TwistType
    reveal_trigger: Optional[str] = None
    forbidden_concurrent_twists: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, entity: Twist) -> "TwistResponse":
        return cls(
            id=entity.id,
            project_id=entity.novel_id,
            description=entity.description,
            status=entity.status,
            created_chapter=entity.created_chapter,
            twist_type=entity.twist_type,
            reveal_trigger=entity.reveal_trigger,
            forbidden_concurrent_twists=list(entity.forbidden_concurrent_twists),
        )


class TwistListResponse(BaseModel):
    """GET /twists list response."""

    model_config = ConfigDict(extra="forbid")
    data: list[TwistResponse]
    meta: PaginationMeta