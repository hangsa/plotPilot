"""Conflict entity Pydantic DTOs (Request + Update + Response)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity


class ConflictCreateRequest(BaseModel):
    """POST /conflicts body."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=2000)
    created_chapter: int = Field(ge=1)
    involved_characters: list[str] = Field(min_length=1)
    status: AssetStatus = AssetStatus.ACTIVE
    intensity: ConflictIntensity = ConflictIntensity.MEDIUM
    linked_conflicts: list[str] = Field(default_factory=list)


class ConflictUpdateRequest(BaseModel):
    """PATCH /conflicts/{id} body (all fields optional)."""

    model_config = ConfigDict(extra="forbid")

    description: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: Optional[AssetStatus] = None
    intensity: Optional[ConflictIntensity] = None
    involved_characters: Optional[list[str]] = None
    linked_conflicts: Optional[list[str]] = None


class ConflictResponse(BaseModel):
    """GET /conflicts/{id} and list-item unified response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    description: str
    status: AssetStatus
    intensity: ConflictIntensity
    created_chapter: int
    involved_characters: list[str]
    linked_conflicts: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, entity: Conflict) -> "ConflictResponse":
        return cls(
            id=entity.id,
            project_id=entity.novel_id,
            description=entity.description,
            status=entity.status,
            intensity=entity.intensity,
            created_chapter=entity.created_chapter,
            involved_characters=list(entity.involved_characters),
            linked_conflicts=list(entity.linked_conflicts),
        )