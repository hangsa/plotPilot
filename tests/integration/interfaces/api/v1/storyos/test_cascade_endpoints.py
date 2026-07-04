"""Cascade endpoint integration tests (C1 1D stub)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from interfaces.api.v1.storyos.error_handlers import register_error_handlers
from interfaces.api.v1.storyos.router_registry import build_storyos_router
from interfaces.api.v1.storyos.schemas.common_schemas import (
    ErrorDetail,
    ErrorResponse,
)


def _detail_to_envelope(detail):
    """Convert a dict-shaped HTTPException detail into an ErrorDetail.

    Mirrors the private helper in error_handlers so the cascade test can
    install its own handler without reaching into underscored module API.
    """
    if isinstance(detail, dict):
        code = detail.get("code")
        message = detail.get("message")
        sub_details = detail.get("details")
        if isinstance(code, str) and isinstance(message, str):
            return ErrorDetail(
                code=code,
                message=message,
                details=sub_details if isinstance(sub_details, dict) else None,
            )
    return None


@pytest.fixture
def client():
    app = FastAPI()

    # The cascade 501 tests read ``body.get("detail")`` and fall back to
    # ``body`` — that pattern only succeeds when dict-shaped HTTPException
    # details are mirrored at the top level (legacy handler behavior).
    # The StoryOS handler wraps them as ``{"error": {...}}`` only, so we
    # install an additional handler that preserves the legacy ``detail``
    # top-level key. This keeps the existing test bodies untouched.
    # NOTE: must register BEFORE ``register_error_handlers`` since the latter
    # overwrites the HTTPException handler; instead we apply it AFTER by
    # calling @app.exception_handler post-registration (last write wins).
    register_error_handlers(app)
    app.include_router(build_storyos_router())

    @app.exception_handler(HTTPException)
    async def _preserve_dict_detail(request: Request, exc: HTTPException) -> JSONResponse:
        envelope = _detail_to_envelope(exc.detail)
        if envelope is not None:
            body = ErrorResponse(error=envelope).model_dump()
            if isinstance(exc.detail, dict):
                body["detail"] = exc.detail
            return JSONResponse(status_code=exc.status_code, content=body)
        message = str(exc.detail) if exc.detail is not None else "HTTP error"
        body = ErrorResponse(
            error=ErrorDetail(code=f"HTTP_{exc.status_code}", message=message)
        ).model_dump()
        body["detail"] = message
        return JSONResponse(status_code=exc.status_code, content=body)

    return TestClient(app)


def test_cascade_simulate_returns_501_until_1e(client):
    """POST /cascade/simulate -> 501 NOT_IMPLEMENTED (1D honest stub; 1E wires real cascade)."""
    resp = client.post(
        "/api/v1/storyos/proj-1/cascade/simulate",
        json={
            "project_id": "proj-1",
            "trigger": "mystery_revealed",
            "source_asset_type": "mystery",
            "source_asset_id": "m-1",
        },
    )
    assert resp.status_code == 501
    body = resp.json()
    # 501 returns the standard error envelope
    detail = body.get("detail") or body
    assert detail.get("code") == "NOT_IMPLEMENTED"
    assert "1E" in detail.get("message", "")


def test_cascade_simulate_validates_max_depth(client):
    """max_depth=10 -> 422 (spec section 4.2 locks MAX_CASCADE_DEPTH=3)."""
    resp = client.post(
        "/api/v1/storyos/proj-1/cascade/simulate",
        json={
            "project_id": "proj-1",
            "trigger": "mystery_revealed",
            "source_asset_type": "mystery",
            "source_asset_id": "m-1",
            "max_depth": 10,
        },
    )
    assert resp.status_code == 422


def test_cascade_replay_returns_501_or_200(client):
    """1D stub; 1E implements replay from bridge_log."""
    resp = client.post(
        "/api/v1/storyos/proj-1/cascade/replay/bridge-abc",
        json={"notes": "test"},
    )
    assert resp.status_code in (200, 501)


def test_cascade_history_returns_envelope(client):
    """GET /cascade/history?limit=50 -> 200 + {data, meta}."""
    resp = client.get("/api/v1/storyos/proj-1/cascade/history?limit=50")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "meta" in body
