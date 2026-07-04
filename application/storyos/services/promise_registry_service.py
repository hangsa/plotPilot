"""Promise Registry Service。"""
from __future__ import annotations

from dataclasses import replace

from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.promise import Promise


class PromiseRegistryService(GenericRegistryService[Promise]):
    def _apply_update(self, entity: Promise, **kwargs) -> Promise:
        if "status" in kwargs:
            return replace(entity, status=kwargs["status"])
        return entity

    def fulfill(self, promise_id: str, chapter: int) -> Promise:
        p = self.get(promise_id)
        new_p = p.fulfill(chapter)  # 委托给 entity 方法
        self._repo[promise_id] = new_p
        return new_p
