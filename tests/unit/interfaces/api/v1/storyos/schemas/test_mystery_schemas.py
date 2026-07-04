"""Mystery + Clue DTO tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.mystery_schemas import (
    MysteryCreateRequest,
    MysteryUpdateRequest,
    MysteryResponse,
    ClueResponse,
    ClueCreateRequest,
)
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.mystery import Clue, ClueCategory, Mystery


def test_mystery_create_request_minimal():
    req = MysteryCreateRequest(
        project_id="proj-1",
        description="Who killed the magistrate?",
        created_chapter=2,
    )
    assert req.project_id == "proj-1"
    assert req.status == AssetStatus.ACTIVE
    assert req.clues == []
    assert req.related_mystery is None


def test_mystery_create_request_rejects_invalid_status():
    with pytest.raises(ValidationError):
        MysteryCreateRequest(
            project_id="proj-1",
            description="x",
            created_chapter=1,
            status="bogus",
        )


def test_clue_create_request_minimal():
    req = ClueCreateRequest(
        description="Bloody dagger in courtyard",
        source_chapter=3,
        source_location="courtyard",
    )
    assert req.category == ClueCategory.TRUTH
    assert req.status == AssetStatus.PLANTED
    assert req.discovered_in_chapter is None


def test_clue_create_request_rejects_empty_source_location():
    with pytest.raises(ValidationError):
        ClueCreateRequest(
            description="x",
            source_chapter=1,
            source_location="",
        )


def test_mystery_update_request_all_optional():
    req = MysteryUpdateRequest()
    assert req.description is None
    assert req.status is None
    assert req.related_mystery is None


def test_mystery_update_request_partial_update():
    req = MysteryUpdateRequest(status=AssetStatus.RESOLVED, related_mystery="mst-2")
    assert req.status == AssetStatus.RESOLVED
    assert req.related_mystery == "mst-2"


def test_mystery_response_from_domain_entity():
    clue = Clue(
        id="cl-1",
        mystery_id="mst-1",
        description="Dagger",
        source_chapter=3,
        source_location="courtyard",
        category=ClueCategory.IDENTITY,
    )
    entity = Mystery(
        id="mst-1",
        novel_id="proj-1",
        description="Who killed the magistrate?",
        status=AssetStatus.ACTIVE,
        created_chapter=2,
        clues=(clue,),
    )
    resp = MysteryResponse.from_domain(entity)
    assert resp.id == "mst-1"
    assert resp.project_id == "proj-1"
    assert resp.status == AssetStatus.ACTIVE
    assert resp.created_chapter == 2
    assert len(resp.clues) == 1
    assert resp.clues[0].id == "cl-1"
    assert resp.clues[0].category == ClueCategory.IDENTITY


def test_mystery_response_serializes_asset_status_as_string():
    entity = Mystery(
        id="mst-1",
        novel_id="proj-1",
        description="x",
        status=AssetStatus.RESOLVED,
        created_chapter=1,
    )
    resp = MysteryResponse.from_domain(entity)
    data = resp.model_dump()
    assert data["status"] == "resolved"
    assert isinstance(data["status"], str)