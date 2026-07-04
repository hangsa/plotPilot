"""Promise DTO tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.promise_schemas import (
    PromiseCreateRequest,
    PromiseUpdateRequest,
    PromiseResponse,
)
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.promise import Promise


def test_promise_create_request_minimal():
    req = PromiseCreateRequest(
        project_id="proj-1",
        description="Hero will return to save the village",
        made_in_chapter=1,
    )
    assert req.project_id == "proj-1"
    assert req.status == AssetStatus.ACTIVE
    assert req.importance == 50
    assert req.fulfilled_in_chapter is None


def test_promise_create_request_rejects_invalid_status():
    with pytest.raises(ValidationError):
        PromiseCreateRequest(
            project_id="proj-1",
            description="x",
            made_in_chapter=1,
            status="bogus",
        )


def test_promise_create_request_importance_range():
    with pytest.raises(ValidationError):
        PromiseCreateRequest(
            project_id="proj-1",
            description="x",
            made_in_chapter=1,
            importance=150,
        )
    with pytest.raises(ValidationError):
        PromiseCreateRequest(
            project_id="proj-1",
            description="x",
            made_in_chapter=1,
            importance=-1,
        )


def test_promise_update_request_all_optional():
    req = PromiseUpdateRequest()
    assert req.description is None
    assert req.status is None
    assert req.importance is None
    assert req.fulfilled_in_chapter is None


def test_promise_update_request_partial_update():
    req = PromiseUpdateRequest(status=AssetStatus.FULFILLED, fulfilled_in_chapter=20)
    assert req.status == AssetStatus.FULFILLED
    assert req.fulfilled_in_chapter == 20


def test_promise_response_from_domain_entity():
    entity = Promise(
        id="pr-1",
        novel_id="proj-1",
        description="x",
        made_in_chapter=1,
        status=AssetStatus.FULFILLED,
        importance=75,
        fulfilled_in_chapter=20,
    )
    resp = PromiseResponse.from_domain(entity)
    assert resp.id == "pr-1"
    assert resp.project_id == "proj-1"
    assert resp.status == AssetStatus.FULFILLED
    assert resp.importance == 75
    assert resp.made_in_chapter == 1
    assert resp.fulfilled_in_chapter == 20


def test_promise_response_serializes_asset_status_as_string():
    entity = Promise(
        id="pr-1",
        novel_id="proj-1",
        description="x",
        made_in_chapter=1,
        status=AssetStatus.ACTIVE,
        importance=50,
    )
    resp = PromiseResponse.from_domain(entity)
    data = resp.model_dump()
    assert data["status"] == "active"
    assert isinstance(data["status"], str)