"""StoryOS subpackage router: 40 CRUD + (cascade/sflog/migration/health stubs)."""
from __future__ import annotations

from fastapi import APIRouter

from interfaces.api.v1.storyos.crud_factory import build_crud_router
from interfaces.api.v1.storyos.dependencies import (
    get_conflict_service,
    get_expectation_service,
    get_foreshadowing_service,
    get_goal_service,
    get_mystery_service,
    get_promise_service,
    get_reveal_service,
    get_twist_service,
)
from interfaces.api.v1.storyos.routes import (
    cascade_routes,
    health_routes,
    migration_routes,
    sflog_routes,
)
from interfaces.api.v1.storyos.schemas.conflict_schemas import (
    ConflictCreateRequest,
    ConflictResponse,
    ConflictUpdateRequest,
)
from interfaces.api.v1.storyos.schemas.expectation_schemas import (
    ExpectationCreateRequest,
    ExpectationResponse,
    ExpectationUpdateRequest,
)
from interfaces.api.v1.storyos.schemas.foreshadowing_schemas import (
    ForeshadowingCreateRequest,
    ForeshadowingResponse,
    ForeshadowingUpdateRequest,
)
from interfaces.api.v1.storyos.schemas.goal_schemas import (
    GoalCreateRequest,
    GoalResponse,
    GoalUpdateRequest,
)
from interfaces.api.v1.storyos.schemas.mystery_schemas import (
    MysteryCreateRequest,
    MysteryResponse,
    MysteryUpdateRequest,
)
from interfaces.api.v1.storyos.schemas.promise_schemas import (
    PromiseCreateRequest,
    PromiseResponse,
    PromiseUpdateRequest,
)
from interfaces.api.v1.storyos.schemas.reveal_schemas import (
    RevealCreateRequest,
    RevealResponse,
    RevealUpdateRequest,
)
from interfaces.api.v1.storyos.schemas.twist_schemas import (
    TwistCreateRequest,
    TwistResponse,
    TwistUpdateRequest,
)


def build_storyos_router() -> APIRouter:
    """Aggregate all StoryOS endpoints into a single APIRouter.

    A5 scope: registers 8 x 5 = 40 CRUD endpoints plus empty stub routers
    for cascade/sflog/migration/health. Group C (C1-C4) adds handlers to
    those stub routers. Group B (B1/B2) replaces the stub service providers
    in ``dependencies.py`` with real factories.
    """
    router = APIRouter(tags=["storyos"])

    # 8 registries x 5 CRUD = 40 endpoints.
    router.include_router(
        build_crud_router(
            asset_type="conflict",
            service_provider=get_conflict_service,
            create_schema=ConflictCreateRequest,
            update_schema=ConflictUpdateRequest,
            response_schema=ConflictResponse,
        )
    )
    router.include_router(
        build_crud_router(
            asset_type="mystery",
            service_provider=get_mystery_service,
            create_schema=MysteryCreateRequest,
            update_schema=MysteryUpdateRequest,
            response_schema=MysteryResponse,
        )
    )
    router.include_router(
        build_crud_router(
            asset_type="twist",
            service_provider=get_twist_service,
            create_schema=TwistCreateRequest,
            update_schema=TwistUpdateRequest,
            response_schema=TwistResponse,
        )
    )
    router.include_router(
        build_crud_router(
            asset_type="promise",
            service_provider=get_promise_service,
            create_schema=PromiseCreateRequest,
            update_schema=PromiseUpdateRequest,
            response_schema=PromiseResponse,
        )
    )
    router.include_router(
        build_crud_router(
            asset_type="reveal",
            service_provider=get_reveal_service,
            create_schema=RevealCreateRequest,
            update_schema=RevealUpdateRequest,
            response_schema=RevealResponse,
        )
    )
    router.include_router(
        build_crud_router(
            asset_type="expectation",
            service_provider=get_expectation_service,
            create_schema=ExpectationCreateRequest,
            update_schema=ExpectationUpdateRequest,
            response_schema=ExpectationResponse,
        )
    )
    router.include_router(
        build_crud_router(
            asset_type="goal",
            service_provider=get_goal_service,
            create_schema=GoalCreateRequest,
            update_schema=GoalUpdateRequest,
            response_schema=GoalResponse,
        )
    )
    router.include_router(
        build_crud_router(
            asset_type="foreshadowing",
            service_provider=get_foreshadowing_service,
            create_schema=ForeshadowingCreateRequest,
            update_schema=ForeshadowingUpdateRequest,
            response_schema=ForeshadowingResponse,
        )
    )

    # Special endpoints (stubs filled by Group C).
    router.include_router(cascade_routes.router)
    router.include_router(sflog_routes.router)
    router.include_router(migration_routes.router)
    router.include_router(health_routes.router)

    return router