"""Twist DTO tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.twist_schemas import (
    TwistCreateRequest,
    TwistUpdateRequest,
    TwistResponse,
)
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.twist import Twist, TwistType


def test_twist_create_request_minimal():
    req = TwistCreateRequest(
        project_id="proj-1",
        description="The butler is the long-lost heir",
        created_chapter=10,
        twist_type=TwistType.IDENTITY_REVEAL,
    )
    assert req.project_id == "proj-1"
    assert req.status == AssetStatus.ACTIVE
    assert req.twist_type == TwistType.IDENTITY_REVEAL
    assert req.reveal_trigger is None
    assert req.forbidden_concurrent_twists == []


def test_twist_create_request_rejects_invalid_status():
    with pytest.raises(ValidationError):
        TwistCreateRequest(
            project_id="proj-1",
            description="x",
            created_chapter=1,
            twist_type=TwistType.BETRAYAL,
            status="bogus",
        )


def test_twist_create_request_rejects_invalid_twist_type():
    with pytest.raises(ValidationError):
        TwistCreateRequest(
            project_id="proj-1",
            description="x",
            created_chapter=1,
            twist_type="bogus",
        )


def test_twist_update_request_all_optional():
    req = TwistUpdateRequest()
    assert req.description is None
    assert req.status is None
    assert req.twist_type is None
    assert req.reveal_trigger is None
    assert req.forbidden_concurrent_twists is None


def test_twist_update_request_partial_update():
    req = TwistUpdateRequest(status=AssetStatus.REVEALED, twist_type=TwistType.TRUTH_REVEALED)
    assert req.status == AssetStatus.REVEALED
    assert req.twist_type == TwistType.TRUTH_REVEALED


def test_twist_response_from_domain_entity():
    entity = Twist(
        id="tw-1",
        novel_id="proj-1",
        description="x",
        status=AssetStatus.REVEALED,
        created_chapter=5,
        twist_type=TwistType.BETRAYAL,
        reveal_trigger="chapter 7 revelation",
        forbidden_concurrent_twists=("tw-2",),
    )
    resp = TwistResponse.from_domain(entity)
    assert resp.id == "tw-1"
    assert resp.project_id == "proj-1"
    assert resp.status == AssetStatus.REVEALED
    assert resp.twist_type == TwistType.BETRAYAL
    assert resp.reveal_trigger == "chapter 7 revelation"
    assert resp.forbidden_concurrent_twists == ["tw-2"]


def test_twist_response_serializes_asset_status_as_string():
    entity = Twist(
        id="tw-1",
        novel_id="proj-1",
        description="x",
        status=AssetStatus.REVEALED,
        created_chapter=5,
        twist_type=TwistType.SACRIFICE,
    )
    resp = TwistResponse.from_domain(entity)
    data = resp.model_dump()
    assert data["status"] == "revealed"
    assert isinstance(data["status"], str)
    assert data["twist_type"] == "sacrifice"