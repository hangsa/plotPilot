"""Conflict Registry Service。"""
from __future__ import annotations

from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.conflict import Conflict


class ConflictRegistryService(GenericRegistryService[Conflict]):
    def _apply_update(self, entity: Conflict, **kwargs) -> Conflict:
        new = entity
        if kwargs.get("escalate"):
            new = new.escalate()
        if "status" in kwargs:
            new = type(new)(**{**new.__dict__, "status": kwargs["status"]})
        return new
