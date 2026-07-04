"""Conflict DTO tests (canonical blueprint for 7 sibling entities)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.conflict_schemas import (
    ConflictCreateRequest,
    ConflictUpdateRequest,
    ConflictResponse,
)
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity


def test_conflict_create_request_minimal():
    req = ConflictCreateRequest(
        project_id="proj-1",
        description="Lin Yuan vs Shen Mo power struggle",
        created_chapter=3,
        involved_characters=["lin-yuan", "shen-mo"],
    )
    assert req.project_id == "proj-1"
    assert req.status == AssetStatus.ACTIVE
    assert req.intensity == ConflictIntensity.MEDIUM
    assert req.linked_conflicts == []


def test_conflict_create_request_rejects_invalid_status():
    with pytest.raises(ValidationError):
        ConflictCreateRequest(
            project_id="proj-1",
            description="x",
            created_chapter=1,
            involved_characters=["a"],
            status="bogus",
        )


def test_conflict_create_request_intensity_validated_by_entity():
    """DTO accepts ConflictIntensity; entity validates on construction."""
    req = ConflictCreateRequest(
        project_id="proj-1",
        description="x",
        created_chapter=1,
        involved_characters=["a"],
        intensity=ConflictIntensity.CRITICAL,
    )
    assert req.intensity == ConflictIntensity.CRITICAL


def test_conflict_update_request_all_optional():
    req = ConflictUpdateRequest()
    assert req.description is None
    assert req.status is None
    assert req.intensity is None
    assert req.linked_conflicts is None
    assert req.involved_characters is None


def test_conflict_update_request_partial_update():
    req = ConflictUpdateRequest(status=AssetStatus.ESCALATED, intensity=ConflictIntensity.HIGH)
    assert req.status == AssetStatus.ESCALATED
    assert req.intensity == ConflictIntensity.HIGH
    assert req.description is None


def test_conflict_response_from_domain_entity():
    entity = Conflict(
        id="cf-1",
        novel_id="proj-1",
        description="x",
        intensity=ConflictIntensity.HIGH,
        status=AssetStatus.ESCALATED,
        involved_characters=("lin-yuan", "shen-mo"),
        created_chapter=5,
        linked_conflicts=("cf-2",),
    )
    resp = ConflictResponse.from_domain(entity)
    assert resp.id == "cf-1"
    assert resp.project_id == "proj-1"
    assert resp.status == AssetStatus.ESCALATED
    assert resp.intensity == ConflictIntensity.HIGH
    assert resp.created_chapter == 5
    assert resp.involved_characters == ["lin-yuan", "shen-mo"]
    assert resp.linked_conflicts == ["cf-2"]


def test_conflict_response_serializes_asset_status_as_string():
    entity = Conflict(
        id="cf-1",
        novel_id="proj-1",
        description="x",
        intensity=ConflictIntensity.HIGH,
        status=AssetStatus.ESCALATED,
        involved_characters=("a",),
        created_chapter=5,
    )
    resp = ConflictResponse.from_domain(entity)
    data = resp.model_dump()
    assert data["status"] == "escalated"
    assert isinstance(data["status"], str)
    assert data["intensity"] == 3