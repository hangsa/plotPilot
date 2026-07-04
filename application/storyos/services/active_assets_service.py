"""ActiveAssetsService — 构建 ActiveAssetsContext。"""
from __future__ import annotations

from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.mystery_registry_service import MysteryRegistryService
from application.storyos.services.twist_registry_service import TwistRegistryService
from application.storyos.services.promise_registry_service import PromiseRegistryService
from application.storyos.services.reveal_registry_service import RevealRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from application.storyos.services.goal_registry_service import GoalRegistryService
from application.storyos.services.foreshadowing_registry_service import ForeshadowingRegistryService
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext


class ActiveAssetsService:
    def __init__(
        self, conflict_svc=None, mystery_svc=None, twist_svc=None,
        promise_svc=None, reveal_svc=None, expectation_svc=None,
        goal_svc=None, foreshadowing_svc=None,
    ) -> None:
        self._services = {
            "conflict": conflict_svc, "mystery": mystery_svc,
            "twist": twist_svc, "promise": promise_svc,
            "reveal": reveal_svc, "expectation": expectation_svc,
            "goal": goal_svc, "foreshadowing": foreshadowing_svc,
        }

    def build_context(self, novel_id: str, chapter_id: int) -> ActiveAssetsContext:
        kwargs = {"novel_id": novel_id, "chapter_id": chapter_id}
        for asset_type, svc in self._services.items():
            if svc is None:
                continue
            items = [e.__dict__ for e in svc.list() if e.novel_id == novel_id]
            # Enum 转 str
            for item in items:
                for k, v in list(item.items()):
                    if hasattr(v, "value"):
                        item[k] = v.value
            kwargs[f"{asset_type}s"] = items
        return ActiveAssetsContext(**kwargs)
