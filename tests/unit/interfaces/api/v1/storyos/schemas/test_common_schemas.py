"""Common pagination + error envelope DTO tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.common_schemas import (
    PaginationMeta,
    ListResponseEnvelope,
    ErrorDetail,
    ErrorResponse,
)


def test_pagination_meta_defaults():
    p = PaginationMeta(total=100, page=1, page_size=20)
    assert p.total_pages == 5
    assert p.has_next is True
    assert p.has_prev is False


def test_pagination_meta_last_page():
    p = PaginationMeta(total=100, page=5, page_size=20)
    assert p.has_next is False
    assert p.has_prev is True


def test_pagination_meta_validates_non_negative():
    with pytest.raises(ValidationError):
        PaginationMeta(total=-1, page=1, page_size=20)


def test_list_response_envelope_wraps_data():
    from interfaces.api.v1.storyos.schemas.conflict_schemas import ConflictResponse
    env = ListResponseEnvelope[ConflictResponse](
        data=[{"id": "cf-1", "project_id": "proj-1", "description": "x",
               "status": "active", "intensity": 2, "created_chapter": 1,
               "involved_characters": ["a"], "linked_conflicts": []}],
        meta=PaginationMeta(total=1, page=1, page_size=20),
    )
    assert env.data[0].id == "cf-1"
    assert env.meta.total == 1


def test_error_detail_includes_code_and_message():
    err = ErrorDetail(code="FORMAT_ERROR", message="bad input")
    assert err.code == "FORMAT_ERROR"
    assert err.details is None


def test_error_response_envelope():
    resp = ErrorResponse(
        error=ErrorDetail(
            code="NOT_FOUND", message="asset cf-1 not found",
            details={"asset_type": "conflict", "asset_id": "cf-1"},
        )
    )
    out = resp.model_dump()
    assert out["error"]["code"] == "NOT_FOUND"
    assert out["error"]["details"]["asset_id"] == "cf-1"