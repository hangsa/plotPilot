"""Twist Registry Service（含互斥检查）。"""
from __future__ import annotations

from dataclasses import replace

from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.twist import Twist


class TwistRegistryService(GenericRegistryService[Twist]):
    def _apply_update(self, entity: Twist, **kwargs) -> Twist:
        if "status" in kwargs:
            return replace(entity, status=kwargs["status"])
        return entity

    def activate_with_mutex_check(self, twist_id: str) -> Twist:
        t = self.get(twist_id)
        for other_id in t.forbidden_concurrent_twists:
            try:
                other = self.get(other_id)
                if other.status == AssetStatus.ACTIVE:
                    raise ValueError(
                        f"Twist {twist_id} has forbidden concurrent active Twist {other_id}"
                    )
            except KeyError:
                continue
        new_t = replace(t, status=AssetStatus.ACTIVE)
        self._repo[twist_id] = new_t
        return new_t
