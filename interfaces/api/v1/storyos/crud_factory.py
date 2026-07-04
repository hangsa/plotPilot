"""CRUD route boilerplate generator (8 registries x 5 CRUD = 40 endpoints share one template)."""
from __future__ import annotations

from typing import Any, Callable, Generic, Optional, Protocol, Type, TypeVar

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel

from interfaces.api.v1.storyos.schemas.common_schemas import (
    ListResponseEnvelope,
    PaginationMeta,
)

TCreate = TypeVar("TCreate", bound=BaseModel)
TUpdate = TypeVar("TUpdate", bound=BaseModel)
TResponse = TypeVar("TResponse", bound=BaseModel)
TEntity = TypeVar("TEntity")


class CRUDService(Protocol, Generic[TEntity, TCreate, TUpdate]):
    """Protocol every registry service must satisfy."""

    async def list(
        self,
        project_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TEntity], int]: ...

    async def get(self, project_id: str, asset_id: str) -> Optional[TEntity]: ...

    async def create(self, project_id: str, data: TCreate) -> TEntity: ...

    async def update(
        self, project_id: str, asset_id: str, data: TUpdate
    ) -> Optional[TEntity]: ...

    async def delete(self, project_id: str, asset_id: str) -> None: ...


def _to_response(response_schema: Type[TResponse], entity: Any) -> TResponse:
    """Convert a domain entity into a response DTO.

    Prefers the ``from_domain`` classmethod (canonical convention across all
    8 A2 schemas) over ``model_validate`` because some entities rename fields
    (e.g. ``Conflict.novel_id`` -> ``ConflictResponse.project_id``).
    """
    from_domain = getattr(response_schema, "from_domain", None)
    if callable(from_domain):
        return from_domain(entity)
    return response_schema.model_validate(entity)


def build_crud_router(
    asset_type: str,
    service_provider: Callable[..., Any],
    create_schema: Type[TCreate],
    update_schema: Type[TUpdate],
    response_schema: Type[TResponse],
) -> APIRouter:
    """Build an APIRouter with the 5 standard CRUD endpoints.

    Path templates::

        GET    /api/v1/storyos/{project_id}/{asset_type}
        GET    /api/v1/storyos/{project_id}/{asset_type}/{asset_id}
        POST   /api/v1/storyos/{project_id}/{asset_type}
        PATCH  /api/v1/storyos/{project_id}/{asset_type}/{asset_id}
        DELETE /api/v1/storyos/{project_id}/{asset_type}/{asset_id}

    ``service_provider`` is a FastAPI Depends-compatible callable (sync or
    async); tests use ``lambda: fake_service`` while production passes the
    DI factory from task B1/B2.
    """
    router = APIRouter(
        prefix=f"/api/v1/storyos/{{project_id}}/{asset_type}",
        tags=[f"storyos-{asset_type}"],
    )

    @router.get("", response_model=ListResponseEnvelope[response_schema])
    async def list_assets(
        project_id: str = Path(..., min_length=1, max_length=64),
        status_filter: Optional[str] = Query(default=None, alias="status"),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=200),
        service: Any = Depends(service_provider),
    ) -> ListResponseEnvelope[response_schema]:
        items, total = await service.list(
            project_id=project_id,
            status=status_filter,
            page=page,
            page_size=page_size,
        )
        return ListResponseEnvelope[response_schema](
            data=[_to_response(response_schema, item) for item in items],
            meta=PaginationMeta.compute(total=total, page=page, page_size=page_size),
        )

    @router.get("/{asset_id}", response_model=response_schema)
    async def get_asset(
        project_id: str = Path(..., min_length=1, max_length=64),
        asset_id: str = Path(..., min_length=1, max_length=128),
        service: Any = Depends(service_provider),
    ) -> response_schema:
        entity = await service.get(project_id, asset_id)
        if entity is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ASSET_NOT_FOUND",
                    "message": (
                        f"{asset_type} {asset_id} not found in project {project_id}"
                    ),
                    "details": {
                        "asset_type": asset_type,
                        "asset_id": asset_id,
                        "project_id": project_id,
                    },
                },
            )
        return _to_response(response_schema, entity)

    @router.post("", response_model=response_schema, status_code=status.HTTP_201_CREATED)
    async def create_asset(
        data=Body(...),
        project_id: str = Path(..., min_length=1, max_length=64),
        service: Any = Depends(service_provider),
    ) -> response_schema:
        entity = await service.create(project_id, data)
        return _to_response(response_schema, entity)

    create_asset.__annotations__["data"] = create_schema

    @router.patch("/{asset_id}", response_model=response_schema)
    async def update_asset(
        data=Body(...),
        project_id: str = Path(..., min_length=1, max_length=64),
        asset_id: str = Path(..., min_length=1, max_length=128),
        service: Any = Depends(service_provider),
    ) -> response_schema:
        entity = await service.update(project_id, asset_id, data)
        if entity is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ASSET_NOT_FOUND",
                    "message": f"{asset_type} {asset_id} not found",
                },
            )
        return _to_response(response_schema, entity)

    update_asset.__annotations__["data"] = update_schema

    @router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_asset(
        project_id: str = Path(..., min_length=1, max_length=64),
        asset_id: str = Path(..., min_length=1, max_length=128),
        service: Any = Depends(service_provider),
    ) -> None:
        await service.delete(project_id, asset_id)

    return router