"""StoryOS FastAPI dependency providers (stubs for A5; replaced by B1/C1-C4)."""
from __future__ import annotations

from typing import Any


def _not_implemented(service_name: str) -> None:
    """Raise the placeholder error used by all A5 stub providers."""
    raise NotImplementedError(
        f"{service_name} provider not yet wired — see tasks B1 / C1-C4"
    )


async def get_conflict_service() -> Any:
    """Group B (B1) will replace this with a real ConflictService factory."""
    _not_implemented("get_conflict_service")


async def get_mystery_service() -> Any:
    """Group B (B1) will replace this with a real MysteryService factory."""
    _not_implemented("get_mystery_service")


async def get_twist_service() -> Any:
    """Group B (B2) will replace this with a real TwistService factory."""
    _not_implemented("get_twist_service")


async def get_promise_service() -> Any:
    """Group B (B1) will replace this with a real PromiseService factory."""
    _not_implemented("get_promise_service")


async def get_reveal_service() -> Any:
    """Group B (B2) will replace this with a real RevealService factory."""
    _not_implemented("get_reveal_service")


async def get_expectation_service() -> Any:
    """Group B (B2) will replace this with a real ExpectationService factory."""
    _not_implemented("get_expectation_service")


async def get_goal_service() -> Any:
    """Group B (B1) will replace this with a real GoalService factory."""
    _not_implemented("get_goal_service")


async def get_foreshadowing_service() -> Any:
    """Group B (B2) will replace this with a real ForeshadowingService factory."""
    _not_implemented("get_foreshadowing_service")


async def get_cascade_service() -> Any:
    """Group C (C1) will replace this with a real CascadeService factory."""
    _not_implemented("get_cascade_service")


async def get_sflog_service() -> Any:
    """Group C (C2) will replace this with a real SFLogService factory."""
    _not_implemented("get_sflog_service")


async def get_migration_service() -> Any:
    """Group C (C3) will replace this with a real MigrationService factory."""
    _not_implemented("get_migration_service")


async def get_health_service() -> Any:
    """Group C (C4) will replace this with a real HealthService factory."""
    _not_implemented("get_health_service")


async def get_metrics_service() -> Any:
    """Group C (C4) will replace this with a real MetricsService factory."""
    _not_implemented("get_metrics_service")