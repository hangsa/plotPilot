"""StoryOS FastAPI dependency providers with adapter layer over 1B registry services."""
from __future__ import annotations

from dataclasses import replace
from typing import Generic, Optional, TypeVar
from uuid import uuid4

from application.storyos.services.conflict_registry_service import (
    ConflictRegistryService,
)
from application.storyos.services.goal_registry_service import GoalRegistryService
from application.storyos.services.mystery_registry_service import (
    MysteryRegistryService,
)
from application.storyos.services.promise_registry_service import (
    PromiseRegistryService,
)
from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.entities.goal import Goal, ProgressMarker
from domain.storyos.entities.mystery import Mystery
from domain.storyos.entities.promise import Promise

TCreate = TypeVar("TCreate")
TUpdate = TypeVar("TUpdate")
TEntity = TypeVar("TEntity")


class _BaseAPIAdapter(Generic[TEntity, TCreate, TUpdate]):
    """Translate (project_id, status, page, page_size, DTO) to GenericRegistryService.

    1B ``GenericRegistryService`` exposes create/get/update/delete/list keyed by
    ``asset_id`` only. The CRUD factory expects project-scoped filtering plus
    pagination, so each adapter owns a singleton service instance and
    filters/paginates on read paths.
    """

    def __init__(self, service: GenericRegistryService) -> None:
        self._svc = service

    def _scope(self) -> list[TEntity]:
        return list(self._svc.list())

    async def list(
        self,
        project_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[TEntity], int]:
        raise NotImplementedError

    async def get(self, project_id: str, asset_id: str) -> Optional[TEntity]:
        raise NotImplementedError

    async def create(self, project_id: str, data: TCreate) -> TEntity:
        raise NotImplementedError

    async def update(
        self, project_id: str, asset_id: str, data: TUpdate
    ) -> Optional[TEntity]:
        raise NotImplementedError

    async def delete(self, project_id: str, asset_id: str) -> None:
        raise NotImplementedError


class ConflictAPIAdapter(_BaseAPIAdapter[Conflict, object, object]):
    """Adapter wrapping ``ConflictRegistryService`` for the CRUD factory."""

    async def list(
        self,
        project_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Conflict], int]:
        items = [c for c in self._scope() if c.novel_id == project_id]
        if status:
            items = [c for c in items if c.status.value == status]
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    async def get(self, project_id: str, asset_id: str) -> Optional[Conflict]:
        try:
            entity = self._svc.get(asset_id)
        except KeyError:
            return None
        if entity.novel_id != project_id:
            return None
        return entity

    async def create(self, project_id: str, data) -> Conflict:
        involved = tuple(data.involved_characters) if data.involved_characters else ("unknown",)
        entity = Conflict(
            id=str(uuid4()),
            novel_id=project_id,
            description=data.description,
            intensity=data.intensity,
            status=data.status,
            involved_characters=involved,
            created_chapter=data.created_chapter,
            linked_conflicts=tuple(data.linked_conflicts),
        )
        return self._svc.create(entity)

    async def update(self, project_id: str, asset_id: str, data) -> Optional[Conflict]:
        try:
            old = self._svc.get(asset_id)
        except KeyError:
            return None
        if old.novel_id != project_id:
            return None
        updates = data.model_dump(exclude_unset=True)
        # Pydantic field names map 1:1 to dataclass fields except status / intensity
        # which are AssetStatus / ConflictIntensity already (Pydantic enums stay as-is).
        replace_kwargs: dict = {}
        for key, value in updates.items():
            replace_kwargs[key] = value
        new = replace(old, **replace_kwargs)
        self._svc.delete(asset_id)  # force replace via create path
        self._svc.create(new)
        return new

    async def delete(self, project_id: str, asset_id: str) -> None:
        existing = await self.get(project_id, asset_id)
        if existing is None:
            return
        self._svc.delete(asset_id)


class MysteryAPIAdapter(_BaseAPIAdapter[Mystery, object, object]):
    """Adapter wrapping ``MysteryRegistryService`` for the CRUD factory."""

    async def list(
        self,
        project_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Mystery], int]:
        items = [m for m in self._scope() if m.novel_id == project_id]
        if status:
            items = [m for m in items if m.status.value == status]
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    async def get(self, project_id: str, asset_id: str) -> Optional[Mystery]:
        try:
            entity = self._svc.get(asset_id)
        except KeyError:
            return None
        if entity.novel_id != project_id:
            return None
        return entity

    async def create(self, project_id: str, data) -> Mystery:
        from interfaces.api.v1.storyos.schemas.mystery_schemas import ClueCreateRequest

        clues: list = []
        for i, raw in enumerate(data.clues or []):
            clue_req = ClueCreateRequest.model_validate(raw) if not isinstance(raw, ClueCreateRequest) else raw
            from domain.storyos.entities.mystery import Clue
            clues.append(
                Clue(
                    id=f"{asset_id_seed()}-clue-{i}",
                    mystery_id="placeholder",
                    description=clue_req.description,
                    source_chapter=clue_req.source_chapter,
                    source_location=clue_req.source_location,
                    category=clue_req.category,
                    status=clue_req.status,
                    discovered_in_chapter=clue_req.discovered_in_chapter,
                    invalidated_in_chapter=clue_req.invalidated_in_chapter,
                )
            )
        mystery_id = asset_id_seed()
        clues_with_id = tuple(
            replace(c, mystery_id=mystery_id) for c in clues
        )
        entity = Mystery(
            id=mystery_id,
            novel_id=project_id,
            description=data.description,
            status=data.status,
            created_chapter=data.created_chapter,
            clues=clues_with_id,
            related_mystery=data.related_mystery,
        )
        return self._svc.create(entity)

    async def update(self, project_id: str, asset_id: str, data) -> Optional[Mystery]:
        try:
            old = self._svc.get(asset_id)
        except KeyError:
            return None
        if old.novel_id != project_id:
            return None
        updates = data.model_dump(exclude_unset=True)
        new = replace(old, **updates)
        self._svc.delete(asset_id)
        self._svc.create(new)
        return new

    async def delete(self, project_id: str, asset_id: str) -> None:
        existing = await self.get(project_id, asset_id)
        if existing is None:
            return
        self._svc.delete(asset_id)


class PromiseAPIAdapter(_BaseAPIAdapter[Promise, object, object]):
    """Adapter wrapping ``PromiseRegistryService`` for the CRUD factory."""

    async def list(
        self,
        project_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Promise], int]:
        items = [p for p in self._scope() if p.novel_id == project_id]
        if status:
            items = [p for p in items if p.status.value == status]
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    async def get(self, project_id: str, asset_id: str) -> Optional[Promise]:
        try:
            entity = self._svc.get(asset_id)
        except KeyError:
            return None
        if entity.novel_id != project_id:
            return None
        return entity

    async def create(self, project_id: str, data) -> Promise:
        entity = Promise(
            id=str(uuid4()),
            novel_id=project_id,
            description=data.description,
            made_in_chapter=data.made_in_chapter,
            status=data.status,
            importance=data.importance,
            fulfilled_in_chapter=data.fulfilled_in_chapter,
        )
        return self._svc.create(entity)

    async def update(self, project_id: str, asset_id: str, data) -> Optional[Promise]:
        try:
            old = self._svc.get(asset_id)
        except KeyError:
            return None
        if old.novel_id != project_id:
            return None
        updates = data.model_dump(exclude_unset=True)
        # Map project_id (if present) -> novel_id to mirror entity field naming
        updates.pop("project_id", None)
        new = replace(old, **updates)
        self._svc.delete(asset_id)
        self._svc.create(new)
        return new

    async def delete(self, project_id: str, asset_id: str) -> None:
        existing = await self.get(project_id, asset_id)
        if existing is None:
            return
        self._svc.delete(asset_id)


class GoalAPIAdapter(_BaseAPIAdapter[Goal, object, object]):
    """Adapter wrapping ``GoalRegistryService`` for the CRUD factory."""

    async def list(
        self,
        project_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Goal], int]:
        items = [g for g in self._scope() if g.novel_id == project_id]
        if status:
            items = [g for g in items if g.status.value == status]
        total = len(items)
        start = (page - 1) * page_size
        return items[start:start + page_size], total

    async def get(self, project_id: str, asset_id: str) -> Optional[Goal]:
        try:
            entity = self._svc.get(asset_id)
        except KeyError:
            return None
        if entity.novel_id != project_id:
            return None
        return entity

    async def create(self, project_id: str, data) -> Goal:
        entity = Goal(
            id=str(uuid4()),
            novel_id=project_id,
            description=data.description,
            status=data.status,
            created_chapter=data.created_chapter,
            current_progress=data.current_progress,
        )
        return self._svc.create(entity)

    async def update(self, project_id: str, asset_id: str, data) -> Optional[Goal]:
        try:
            old = self._svc.get(asset_id)
        except KeyError:
            return None
        if old.novel_id != project_id:
            return None
        updates = data.model_dump(exclude_unset=True)
        updates.pop("project_id", None)
        new = replace(old, **updates)
        self._svc.delete(asset_id)
        self._svc.create(new)
        return new

    async def delete(self, project_id: str, asset_id: str) -> None:
        existing = await self.get(project_id, asset_id)
        if existing is None:
            return
        self._svc.delete(asset_id)


# Module-level singletons so all requests in a process share the in-memory dict.
# Tests can reset via the ``reset_*_adapter`` hooks below for isolation.

_conflict_adapter: Optional[ConflictAPIAdapter] = None
_mystery_adapter: Optional[MysteryAPIAdapter] = None
_promise_adapter: Optional[PromiseAPIAdapter] = None
_goal_adapter: Optional[GoalAPIAdapter] = None


def _new_conflict_adapter() -> ConflictAPIAdapter:
    return ConflictAPIAdapter(ConflictRegistryService())


def _new_mystery_adapter() -> MysteryAPIAdapter:
    return MysteryAPIAdapter(MysteryRegistryService())


def _new_promise_adapter() -> PromiseAPIAdapter:
    return PromiseAPIAdapter(PromiseRegistryService())


def _new_goal_adapter() -> GoalAPIAdapter:
    return GoalAPIAdapter(GoalRegistryService())


def _get_conflict_adapter() -> ConflictAPIAdapter:
    global _conflict_adapter
    if _conflict_adapter is None:
        _conflict_adapter = _new_conflict_adapter()
    return _conflict_adapter


def _get_mystery_adapter() -> MysteryAPIAdapter:
    global _mystery_adapter
    if _mystery_adapter is None:
        _mystery_adapter = _new_mystery_adapter()
    return _mystery_adapter


def _get_promise_adapter() -> PromiseAPIAdapter:
    global _promise_adapter
    if _promise_adapter is None:
        _promise_adapter = _new_promise_adapter()
    return _promise_adapter


def _get_goal_adapter() -> GoalAPIAdapter:
    global _goal_adapter
    if _goal_adapter is None:
        _goal_adapter = _new_goal_adapter()
    return _goal_adapter


def reset_conflict_adapter() -> None:
    """Test hook: clear in-memory state for the conflict registry."""
    global _conflict_adapter
    _conflict_adapter = None


def reset_mystery_adapter() -> None:
    """Test hook: clear in-memory state for the mystery registry."""
    global _mystery_adapter
    _mystery_adapter = None


def reset_promise_adapter() -> None:
    """Test hook: clear in-memory state for the promise registry."""
    global _promise_adapter
    _promise_adapter = None


def reset_goal_adapter() -> None:
    """Test hook: clear in-memory state for the goal registry."""
    global _goal_adapter
    _goal_adapter = None


async def get_conflict_service() -> ConflictAPIAdapter:
    """B1 DI factory: returns ConflictAPIAdapter singleton."""
    return _get_conflict_adapter()


async def get_mystery_service() -> MysteryAPIAdapter:
    """B1 DI factory: returns MysteryAPIAdapter singleton."""
    return _get_mystery_adapter()


async def get_promise_service() -> PromiseAPIAdapter:
    """B1 DI factory: returns PromiseAPIAdapter singleton."""
    return _get_promise_adapter()


async def get_goal_service() -> GoalAPIAdapter:
    """B1 DI factory: returns GoalAPIAdapter singleton."""
    return _get_goal_adapter()


# Group B (B2) will replace these stubs with real Twist/Reveal/Expectation/Foreshadowing
# factories that similarly return per-registry adapter singletons.
async def get_twist_service() -> None:
    _not_implemented("get_twist_service")


async def get_reveal_service() -> None:
    _not_implemented("get_reveal_service")


async def get_expectation_service() -> None:
    _not_implemented("get_expectation_service")


async def get_foreshadowing_service() -> None:
    _not_implemented("get_foreshadowing_service")


# Group C (C1-C4) will replace these stubs.
async def get_cascade_service() -> None:
    _not_implemented("get_cascade_service")


async def get_sflog_service() -> None:
    _not_implemented("get_sflog_service")


async def get_migration_service() -> None:
    _not_implemented("get_migration_service")


async def get_health_service() -> None:
    _not_implemented("get_health_service")


async def get_metrics_service() -> None:
    _not_implemented("get_metrics_service")


def _not_implemented(service_name: str) -> None:
    """Placeholder error used by Group B/C stub providers (B2, C1-C4)."""
    raise NotImplementedError(
        f"{service_name} provider not yet wired — see tasks B2 / C1-C4"
    )


def asset_id_seed() -> str:
    """Generate a UUID string for use as asset_id seed."""
    return str(uuid4())
