"""SnapshotProjector — 投影 8 registry 状态到 snapshot（供 1D API/前端读取）。"""
from __future__ import annotations

from dataclasses import asdict
from enum import Enum

from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.mystery_registry_service import MysteryRegistryService
from application.storyos.services.twist_registry_service import TwistRegistryService
from application.storyos.services.promise_registry_service import PromiseRegistryService
from application.storyos.services.reveal_registry_service import RevealRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from application.storyos.services.goal_registry_service import GoalRegistryService
from application.storyos.services.foreshadowing_registry_service import ForeshadowingRegistryService


class SnapshotProjector:
    def __init__(
        self,
        conflict_svc: ConflictRegistryService | None = None,
        mystery_svc: MysteryRegistryService | None = None,
        twist_svc: TwistRegistryService | None = None,
        promise_svc: PromiseRegistryService | None = None,
        reveal_svc: RevealRegistryService | None = None,
        expectation_svc: ExpectationRegistryService | None = None,
        goal_svc: GoalRegistryService | None = None,
        foreshadowing_svc: ForeshadowingRegistryService | None = None,
    ) -> None:
        self._services = {
            "conflict": conflict_svc,
            "mystery": mystery_svc,
            "twist": twist_svc,
            "promise": promise_svc,
            "reveal": reveal_svc,
            "expectation": expectation_svc,
            "goal": goal_svc,
            "foreshadowing": foreshadowing_svc,
        }

    def project(self, novel_id: str) -> dict:
        snap: dict = {}
        for asset_type, svc in self._services.items():
            if svc is None:
                continue
            snap[asset_type] = {}
            for entity in svc.list():
                if entity.novel_id == novel_id:
                    snap[asset_type][entity.id] = self._entity_to_dict(entity)
        return snap

    @staticmethod
    def _entity_to_dict(entity) -> dict:
        d = asdict(entity)
        # Enum → str name. AssetStatus uses str-valued enums (value == name);
        # ConflictIntensity is IntEnum (value is an int) — we serialize to .name
        # so the 1D API/frontend receives human-readable strings consistently.
        for k, v in list(d.items()):
            if isinstance(v, Enum):
                d[k] = v.name
        return d
