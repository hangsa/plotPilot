"""Mystery + Clue entity Pydantic DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.mystery import Clue, ClueCategory, Mystery
from interfaces.api.v1.storyos.schemas.common_schemas import PaginationMeta


class ClueCreateRequest(BaseModel):
    """POST /mysteries/{id}/clues body."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, max_length=2000)
    source_chapter: int = Field(ge=1)
    source_location: str = Field(min_length=1, max_length=200)
    category: ClueCategory = ClueCategory.TRUTH
    status: AssetStatus = AssetStatus.PLANTED
    discovered_in_chapter: Optional[int] = Field(default=None, ge=1)
    invalidated_in_chapter: Optional[int] = Field(default=None, ge=1)


class ClueResponse(BaseModel):
    """Clue serialization."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    description: str
    source_chapter: int
    source_location: str
    category: ClueCategory
    status: AssetStatus
    discovered_in_chapter: Optional[int] = None
    invalidated_in_chapter: Optional[int] = None

    @classmethod
    def from_domain(cls, entity: Clue) -> "ClueResponse":
        return cls(
            id=entity.id,
            description=entity.description,
            source_chapter=entity.source_chapter,
            source_location=entity.source_location,
            category=entity.category,
            status=entity.status,
            discovered_in_chapter=entity.discovered_in_chapter,
            invalidated_in_chapter=entity.invalidated_in_chapter,
        )


class MysteryCreateRequest(BaseModel):
    """POST /mysteries body."""

    model_config = ConfigDict(extra="forbid")

    project_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=2000)
    created_chapter: int = Field(ge=1)
    status: AssetStatus = AssetStatus.ACTIVE
    clues: list[ClueCreateRequest] = Field(default_factory=list)
    related_mystery: Optional[str] = None


class MysteryUpdateRequest(BaseModel):
    """PATCH /mysteries/{id} body."""

    model_config = ConfigDict(extra="forbid")

    description: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: Optional[AssetStatus] = None
    related_mystery: Optional[str] = None


class MysteryResponse(BaseModel):
    """GET /mysteries/{id} response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    related_mystery: Optional[str] = None
    clues: list[ClueResponse] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, entity: Mystery) -> "MysteryResponse":
        return cls(
            id=entity.id,
            project_id=entity.novel_id,
            description=entity.description,
            status=entity.status,
            created_chapter=entity.created_chapter,
            related_mystery=entity.related_mystery,
            clues=[ClueResponse.from_domain(c) for c in entity.clues],
        )


class ClueListResponse(BaseModel):
    """GET /clues list response."""

    model_config = ConfigDict(extra="forbid")
    data: list[ClueResponse]
    meta: PaginationMeta


class MysteryListResponse(BaseModel):
    """GET /mysteries list response."""

    model_config = ConfigDict(extra="forbid")
    data: list[MysteryResponse]
    meta: PaginationMeta