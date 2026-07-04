"""Foreshadowing DTO tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.foreshadowing_schemas import (
    ForeshadowingCreateRequest,
    ForeshadowingUpdateRequest,
    ForeshadowingResponse,
)
from domain.storyos.contracts import AssetStatus
from domain.novel.value_objects.foreshadowing import ImportanceLevel
from domain.storyos.entities.foreshadowing import Foreshadowing


def test_foreshadowing_create_request_minimal():
    req = ForeshadowingCreateRequest(
        project_id="proj-1",
        description="The cracked locket will matter later",
        planted_in_chapter=1,
    )
    assert req.project_id == "proj-1"
    assert req.status == AssetStatus.PLANTED
    assert req.importance == ImportanceLevel.MEDIUM
    assert req.suggested_resolve_chapter is None
    assert req.resolved_in_chapter is None


def test_foreshadowing_create_request_rejects_invalid_status():
    with pytest.raises(ValidationError):
        ForeshadowingCreateRequest(
            project_id="proj-1",
            description="x",
            planted_in_chapter=1,
            status="bogus",
        )


def test_foreshadowing_create_request_importance_default():
    req = ForeshadowingCreateRequest(
        project_id="proj-1",
        description="x",
        planted_in_chapter=1,
        importance=ImportanceLevel.CRITICAL,
    )
    assert req.importance == ImportanceLevel.CRITICAL


def test_foreshadowing_update_request_all_optional():
    req = ForeshadowingUpdateRequest()
    assert req.description is None
    assert req.status is None
    assert req.importance is None
    assert req.suggested_resolve_chapter is None
    assert req.resolved_in_chapter is None


def test_foreshadowing_update_request_partial_update():
    req = ForeshadowingUpdateRequest(
        status=AssetStatus.REVEALED,
        resolved_in_chapter=25,
    )
    assert req.status == AssetStatus.REVEALED
    assert req.resolved_in_chapter == 25


def test_foreshadowing_response_from_domain_entity():
    entity = Foreshadowing(
        id="fs-1",
        novel_id="proj-1",
        description="x",
        importance=ImportanceLevel.HIGH,
        status=AssetStatus.PLANTED,
        planted_in_chapter=2,
        suggested_resolve_chapter=20,
    )
    resp = ForeshadowingResponse.from_domain(entity)
    assert resp.id == "fs-1"
    assert resp.project_id == "proj-1"
    assert resp.status == AssetStatus.PLANTED
    assert resp.importance == ImportanceLevel.HIGH
    assert resp.planted_in_chapter == 2
    assert resp.suggested_resolve_chapter == 20
    assert resp.resolved_in_chapter is None


def test_foreshadowing_response_serializes_asset_status_as_string():
    entity = Foreshadowing(
        id="fs-1",
        novel_id="proj-1",
        description="x",
        importance=ImportanceLevel.LOW,
        status=AssetStatus.REVEALED,
        planted_in_chapter=1,
        resolved_in_chapter=10,
    )
    resp = ForeshadowingResponse.from_domain(entity)
    data = resp.model_dump()
    assert data["status"] == "revealed"
    assert isinstance(data["status"], str)