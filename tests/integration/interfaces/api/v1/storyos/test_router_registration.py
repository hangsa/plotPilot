"""StoryOS router registry + global error envelope integration tests."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from interfaces.api.v1.storyos.error_handlers import register_error_handlers
from interfaces.api.v1.storyos.router_registry import build_storyos_router


def test_all_8_assets_have_5_crud_routes():
    """8 asset types x 5 CRUD endpoints = 40 paths registered via OpenAPI."""
    app = FastAPI()
    app.include_router(build_storyos_router())
    schema = app.openapi()
    paths = schema["paths"]

    expected_methods = {"get", "post", "patch", "delete"}
    asset_types = [
        "conflict",
        "mystery",
        "twist",
        "promise",
        "reveal",
        "expectation",
        "goal",
        "foreshadowing",
    ]

    for asset in asset_types:
        list_path = f"/api/v1/storyos/{{project_id}}/{asset}"
        detail_path = f"/api/v1/storyos/{{project_id}}/{asset}/{{asset_id}}"
        assert list_path in paths, f"missing list path for {asset}"
        assert detail_path in paths, f"missing detail path for {asset}"
        list_methods = set(paths[list_path].keys()) & expected_methods
        detail_methods = set(paths[detail_path].keys()) & expected_methods
        assert "get" in list_methods
        assert "post" in list_methods
        assert all(m in detail_methods for m in ("get", "patch", "delete"))


def test_error_envelope_returned_for_validation_error():
    """A Body(...) field with min_length=1 catches empty strings -> 422 envelope.

    The envelope is registered as a global RequestValidationError handler,
    so any Pydantic-validated endpoint that rejects a body will see it. We
    use a minimal inline route here (not a storyos CRUD route) so the test
    does not depend on stub service providers raising NotImplementedError.
    """
    from pydantic import BaseModel, ConfigDict, Field

    class _Payload(BaseModel):
        model_config = ConfigDict(extra="forbid")
        name: str = Field(min_length=1, max_length=64)

    app = FastAPI()
    register_error_handlers(app)

    @app.post("/_probe", response_model=_Payload)
    async def _probe(payload: _Payload) -> _Payload:
        return payload

    client = TestClient(app)
    resp = client.post("/_probe", json={"name": ""})
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Request validation failed"