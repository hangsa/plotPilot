"""Goal entity Pydantic DTOs."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.goal import Goal, ProgressMarker


class GoalCreateRequest(BaseModel):
    """POST /goals body."""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=2000)
    created_chapter: int = Field(ge=1)
    status: AssetStatus = AssetStatus.ACTIVE
    current_progress: ProgressMarker = ProgressMarker.T0


class GoalUpdateRequest(BaseModel):
    """PATCH /goals/{id} body."""

    model_config = ConfigDict(extra="forbid")

    description: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: Optional[AssetStatus] = None
    current_progress: Optional[ProgressMarker] = None


class GoalResponse(BaseModel):
    """GET /goals/{id} response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    current_progress: ProgressMarker

    @classmethod
    def from_domain(cls, entity: Goal) -> "GoalResponse":
        return cls(
            id=entity.id,
            project_id=entity.novel_id,
            description=entity.description,
            status=entity.status,
            created_chapter=entity.created_chapter,
            current_progress=entity.current_progress,
        )