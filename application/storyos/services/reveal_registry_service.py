"""Reveal Registry Service。"""
from __future__ import annotations

from dataclasses import replace

from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.reveal import Reveal


class RevealRegistryService(GenericRegistryService[Reveal]):
    def _apply_update(self, entity: Reveal, **kwargs) -> Reveal:
        if "status" in kwargs:
            return replace(entity, status=kwargs["status"])
        return entity

    def reveal(self, reveal_id: str, chapter: int) -> Reveal:
        r = self.get(reveal_id)
        new_r = r.reveal(chapter)  # 委托给 entity 方法
        self._repo[reveal_id] = new_r
        return new_r
