"""Goal Registry Service。"""
from __future__ import annotations

from dataclasses import replace

from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.goal import Goal


class GoalRegistryService(GenericRegistryService[Goal]):
    def _apply_update(self, entity: Goal, **kwargs) -> Goal:
        if "status" in kwargs:
            return replace(entity, status=kwargs["status"])
        return entity

    def advance(self, goal_id: str, marker) -> Goal:
        g = self.get(goal_id)
        new_g = g.advance(marker)
        self._repo[goal_id] = new_g
        return new_g