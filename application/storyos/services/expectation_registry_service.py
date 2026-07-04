"""Expectation Registry Service。"""
from __future__ import annotations

from dataclasses import replace

from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.expectation import Expectation


class ExpectationRegistryService(GenericRegistryService[Expectation]):
    def _apply_update(self, entity: Expectation, **kwargs) -> Expectation:
        if "status" in kwargs:
            return replace(entity, status=kwargs["status"])
        return entity

    def intensify(self, expectation_id: str, delta: int) -> Expectation:
        e = self.get(expectation_id)
        new_e = e.intensify(delta)  # entity 自己负责 clamp 到 [0, 100]
        self._repo[expectation_id] = new_e
        return new_e