"""crud_factory unit tests."""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from interfaces.api.v1.storyos.crud_factory import build_crud_router
from interfaces.api.v1.storyos.schemas.conflict_schemas import (
    ConflictCreateRequest,
    ConflictUpdateRequest,
    ConflictResponse,
)
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.contracts import AssetStatus


class FakeConflictService:
    """Minimal stub that verifies factory forwards 5 CRUD methods."""

    def __init__(self) -> None:
        self.list_called_with: tuple | None = None
        self.get_called_with: tuple | None = None
        self.create_called_with: tuple | None = None
        self.update_called_with: tuple | None = None
        self.delete_called_with: tuple | None = None
        self._store: dict[str, Conflict] = {}

    async def list(self, project_id, status=None, page=1, page_size=20):
        self.list_called_with = (project_id, status, page, page_size)
        items = [c for c in self._store.values() if c.novel_id == project_id]
        if status:
            items = [c for c in items if c.status.value == status]
        return items, len(items)

    async def get(self, project_id, asset_id):
        self.get_called_with = (project_id, asset_id)
        return self._store.get(asset_id)

    async def create(self, project_id, data):
        self.create_called_with = (project_id, data)
        entity = Conflict(
            id="cf-1",
            novel_id=project_id,
            description=data.description,
            intensity=data.intensity,
            status=data.status,
            involved_characters=tuple(data.involved_characters),
            created_chapter=data.created_chapter,
            linked_conflicts=tuple(data.linked_conflicts),
        )
        self._store[entity.id] = entity
        return entity

    async def update(self, project_id, asset_id, data):
        self.update_called_with = (project_id, asset_id, data)
        old = self._store[asset_id]
        updates = data.model_dump(exclude_unset=True)
        # Translate response field name back to entity field name.
        if "project_id" in updates:
            updates["novel_id"] = updates.pop("project_id")
        new = old.model_copy(update=updates)
        self._store[asset_id] = new
        return new

    async def delete(self, project_id, asset_id):
        self.delete_called_with = (project_id, asset_id)
        del self._store[asset_id]


def test_factory_returns_api_router():
    service = FakeConflictService()
    router = build_crud_router(
        asset_type="conflict",
        service_provider=lambda: service,
        create_schema=ConflictCreateRequest,
        update_schema=ConflictUpdateRequest,
        response_schema=ConflictResponse,
    )
    assert isinstance(router, APIRouter)
    assert len(router.routes) == 5


def test_factory_routes_have_correct_paths():
    service = FakeConflictService()
    router = build_crud_router(
        asset_type="conflict",
        service_provider=lambda: service,
        create_schema=ConflictCreateRequest,
        update_schema=ConflictUpdateRequest,
        response_schema=ConflictResponse,
    )
    paths = {r.path for r in router.routes}
    assert "/api/v1/storyos/{project_id}/conflict" in paths
    assert "/api/v1/storyos/{project_id}/conflict/{asset_id}" in paths


def test_factory_list_route_calls_service_list():
    service = FakeConflictService()
    router = build_crud_router(
        asset_type="conflict",
        service_provider=lambda: service,
        create_schema=ConflictCreateRequest,
        update_schema=ConflictUpdateRequest,
        response_schema=ConflictResponse,
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get(
        "/api/v1/storyos/proj-1/conflict?status=active&page=1&page_size=20"
    )
    assert resp.status_code == 200
    assert service.list_called_with == ("proj-1", "active", 1, 20)


def test_factory_get_route_returns_envelope():
    service = FakeConflictService()
    service._store["cf-1"] = Conflict(
        id="cf-1",
        novel_id="proj-1",
        description="x",
        intensity=ConflictIntensity.MEDIUM,
        status=AssetStatus.ACTIVE,
        involved_characters=("char-a",),
        created_chapter=1,
    )
    router = build_crud_router(
        asset_type="conflict",
        service_provider=lambda: service,
        create_schema=ConflictCreateRequest,
        update_schema=ConflictUpdateRequest,
        response_schema=ConflictResponse,
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/storyos/proj-1/conflict/cf-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "cf-1"


def test_factory_create_route_accepts_body():
    service = FakeConflictService()
    router = build_crud_router(
        asset_type="conflict",
        service_provider=lambda: service,
        create_schema=ConflictCreateRequest,
        update_schema=ConflictUpdateRequest,
        response_schema=ConflictResponse,
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={
            "project_id": "proj-1",
            "description": "x",
            "created_chapter": 1,
            "involved_characters": ["char-a"],
            "status": "active",
            "intensity": 2,
        },
    )
    assert resp.status_code == 201
    assert service.create_called_with is not None