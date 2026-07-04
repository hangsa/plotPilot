"""Reveal DTO tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.reveal_schemas import (
    RevealCreateRequest,
    RevealUpdateRequest,
    RevealResponse,
)
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.reveal import Reveal


def test_reveal_create_request_minimal():
    req = RevealCreateRequest(
        project_id="proj-1",
        content="The protagonist is actually a ghost",
    )
    assert req.project_id == "proj-1"
    assert req.status == AssetStatus.HIDDEN
    assert req.content == "The protagonist is actually a ghost"
    assert req.related_mystery is None
    assert req.linked_to_conflict is None
    assert req.revealed_in_chapter is None


def test_reveal_create_request_rejects_invalid_status():
    with pytest.raises(ValidationError):
        RevealCreateRequest(
            project_id="proj-1",
            content="x",
            status="bogus",
        )


def test_reveal_create_request_rejects_empty_content():
    with pytest.raises(ValidationError):
        RevealCreateRequest(
            project_id="proj-1",
            content="",
        )


def test_reveal_update_request_all_optional():
    req = RevealUpdateRequest()
    assert req.content is None
    assert req.status is None
    assert req.related_mystery is None
    assert req.linked_to_conflict is None
    assert req.revealed_in_chapter is None


def test_reveal_update_request_partial_update():
    req = RevealUpdateRequest(status=AssetStatus.REVEALED, revealed_in_chapter=15)
    assert req.status == AssetStatus.REVEALED
    assert req.revealed_in_chapter == 15


def test_reveal_response_from_domain_entity():
    entity = Reveal(
        id="rv-1",
        novel_id="proj-1",
        content="x",
        status=AssetStatus.REVEALED,
        related_mystery="mst-1",
        linked_to_conflict="cf-1",
        revealed_in_chapter=15,
    )
    resp = RevealResponse.from_domain(entity)
    assert resp.id == "rv-1"
    assert resp.project_id == "proj-1"
    assert resp.content == "x"
    assert resp.status == AssetStatus.REVEALED
    assert resp.related_mystery == "mst-1"
    assert resp.linked_to_conflict == "cf-1"
    assert resp.revealed_in_chapter == 15


def test_reveal_response_serializes_asset_status_as_string():
    entity = Reveal(
        id="rv-1",
        novel_id="proj-1",
        content="x",
        status=AssetStatus.REVEALED,
        related_mystery=None,
        revealed_in_chapter=10,
    )
    resp = RevealResponse.from_domain(entity)
    data = resp.model_dump()
    assert data["status"] == "revealed"
    assert isinstance(data["status"], str)