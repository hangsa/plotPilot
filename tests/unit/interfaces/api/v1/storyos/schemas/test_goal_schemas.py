"""Goal DTO tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.goal_schemas import (
    GoalCreateRequest,
    GoalUpdateRequest,
    GoalResponse,
)
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.goal import Goal, ProgressMarker


def test_goal_create_request_minimal():
    req = GoalCreateRequest(
        project_id="proj-1",
        description="Hero must reach the capital",
        created_chapter=1,
    )
    assert req.project_id == "proj-1"
    assert req.status == AssetStatus.ACTIVE
    assert req.current_progress == ProgressMarker.T0


def test_goal_create_request_rejects_invalid_status():
    with pytest.raises(ValidationError):
        GoalCreateRequest(
            project_id="proj-1",
            description="x",
            created_chapter=1,
            status="bogus",
        )


def test_goal_create_request_progress_marker():
    req = GoalCreateRequest(
        project_id="proj-1",
        description="x",
        created_chapter=1,
        current_progress=ProgressMarker.T3,
    )
    assert req.current_progress == ProgressMarker.T3


def test_goal_update_request_all_optional():
    req = GoalUpdateRequest()
    assert req.description is None
    assert req.status is None
    assert req.current_progress is None


def test_goal_update_request_partial_update():
    req = GoalUpdateRequest(status=AssetStatus.FULFILLED, current_progress=ProgressMarker.T9)
    assert req.status == AssetStatus.FULFILLED
    assert req.current_progress == ProgressMarker.T9


def test_goal_response_from_domain_entity():
    entity = Goal(
        id="go-1",
        novel_id="proj-1",
        description="x",
        status=AssetStatus.DEVELOPING,
        created_chapter=1,
        current_progress=ProgressMarker.T4,
    )
    resp = GoalResponse.from_domain(entity)
    assert resp.id == "go-1"
    assert resp.project_id == "proj-1"
    assert resp.status == AssetStatus.DEVELOPING
    assert resp.current_progress == ProgressMarker.T4
    assert resp.created_chapter == 1


def test_goal_response_serializes_asset_status_as_string():
    entity = Goal(
        id="go-1",
        novel_id="proj-1",
        description="x",
        status=AssetStatus.FULFILLED,
        created_chapter=1,
        current_progress=ProgressMarker.T9,
    )
    resp = GoalResponse.from_domain(entity)
    data = resp.model_dump()
    assert data["status"] == "fulfilled"
    assert isinstance(data["status"], str)
    assert data["current_progress"] == 9