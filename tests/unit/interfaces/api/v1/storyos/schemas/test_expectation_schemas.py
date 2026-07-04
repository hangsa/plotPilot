"""Expectation DTO tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.expectation_schemas import (
    ExpectationCreateRequest,
    ExpectationUpdateRequest,
    ExpectationResponse,
)
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.expectation import Expectation


def test_expectation_create_request_minimal():
    req = ExpectationCreateRequest(
        project_id="proj-1",
        description="Reader expects the hero to save the village",
        created_chapter=1,
    )
    assert req.project_id == "proj-1"
    assert req.status == AssetStatus.ACTIVE
    assert req.intensity == 50


def test_expectation_create_request_rejects_invalid_status():
    with pytest.raises(ValidationError):
        ExpectationCreateRequest(
            project_id="proj-1",
            description="x",
            created_chapter=1,
            status="bogus",
        )


def test_expectation_create_request_intensity_range():
    with pytest.raises(ValidationError):
        ExpectationCreateRequest(
            project_id="proj-1",
            description="x",
            created_chapter=1,
            intensity=150,
        )
    with pytest.raises(ValidationError):
        ExpectationCreateRequest(
            project_id="proj-1",
            description="x",
            created_chapter=1,
            intensity=-1,
        )


def test_expectation_update_request_all_optional():
    req = ExpectationUpdateRequest()
    assert req.description is None
    assert req.status is None
    assert req.intensity is None


def test_expectation_update_request_partial_update():
    req = ExpectationUpdateRequest(status=AssetStatus.FULFILLED, intensity=10)
    assert req.status == AssetStatus.FULFILLED
    assert req.intensity == 10


def test_expectation_response_from_domain_entity():
    entity = Expectation(
        id="ex-1",
        novel_id="proj-1",
        description="x",
        status=AssetStatus.ESCALATED,
        created_chapter=5,
        intensity=80,
    )
    resp = ExpectationResponse.from_domain(entity)
    assert resp.id == "ex-1"
    assert resp.project_id == "proj-1"
    assert resp.status == AssetStatus.ESCALATED
    assert resp.intensity == 80
    assert resp.created_chapter == 5


def test_expectation_response_serializes_asset_status_as_string():
    entity = Expectation(
        id="ex-1",
        novel_id="proj-1",
        description="x",
        status=AssetStatus.FULFILLED,
        created_chapter=5,
        intensity=10,
    )
    resp = ExpectationResponse.from_domain(entity)
    data = resp.model_dump()
    assert data["status"] == "fulfilled"
    assert isinstance(data["status"], str)