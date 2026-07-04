"""Foreshadowing Registry Service。"""
from __future__ import annotations

from dataclasses import replace

from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.foreshadowing import Foreshadowing


class ForeshadowingRegistryService(GenericRegistryService[Foreshadowing]):
    def _apply_update(self, entity: Foreshadowing, **kwargs) -> Foreshadowing:
        if "status" in kwargs:
            return replace(entity, status=kwargs["status"])
        return entity

    def resolve(self, foreshadowing_id: str, chapter: int) -> Foreshadowing:
        f = self.get(foreshadowing_id)
        new_f = f.resolve(chapter)
        self._repo[foreshadowing_id] = new_f
        return new_f

    def abandon(self, foreshadowing_id: str, chapter: int) -> Foreshadowing:
        f = self.get(foreshadowing_id)
        new_f = f.abandon(chapter)
        self._repo[foreshadowing_id] = new_f
        return new_f