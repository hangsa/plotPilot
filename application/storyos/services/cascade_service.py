"""CascadeService — BFS 级联执行（spec §4.2 锁定 MAX_DEPTH=3）。"""
from __future__ import annotations

from domain.storyos.contracts import AssetStatus
from domain.storyos.value_objects.cascade import CascadeResult, CascadeRules, CascadeStep
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService


class CascadeService:
    def __init__(
        self,
        conflict_svc=None, mystery_svc=None, twist_svc=None,
        promise_svc=None, reveal_svc=None, expectation_svc=None,
        goal_svc=None, foreshadowing_svc=None,
        max_depth: int = 3,
    ):
        self.conflict_svc = conflict_svc
        self.mystery_svc = mystery_svc
        self.twist_svc = twist_svc
        self.promise_svc = promise_svc
        self.reveal_svc = reveal_svc
        self.expectation_svc = expectation_svc
        self.goal_svc = goal_svc
        self.foreshadowing_svc = foreshadowing_svc
        self.max_depth = max_depth
        self._rules = CascadeRules()

    def execute(self, steps: list[CascadeStep]) -> CascadeResult:
        """BFS 执行级联步骤。"""
        result = CascadeResult()
        visited: set[str] = set()
        for step in steps:
            if step.source_asset_id in visited:
                result.blocked_steps.append(step)
                continue
            check = self._rules.apply_to(step, visited, self.max_depth)
            if check["would_create_cycle"] or check["depth_exceeded"]:
                result.blocked_steps.append(step)
                continue
            visited.add(step.target_asset_id)
            if self._apply_step(step):
                result.steps_executed.append(step)
            else:
                result.blocked_steps.append(step)
        return result.model_copy(update={"max_depth_reached": len(visited)})

    def _apply_step(self, step: CascadeStep) -> bool:
        target_svc = self._get_service(step.target_asset_type)
        if target_svc is None:
            return False  # 软失败：未知 type
        try:
            if step.intensity_delta is not None and step.target_asset_type == "expectation":
                target_svc.intensify(step.target_asset_id, step.intensity_delta)
            elif step.new_status is not None:
                target_svc.update(step.target_asset_id, status=step.new_status)
            return True
        except (KeyError, AttributeError, ValueError) as e:
            # 孤儿或非法转换 → 软失败，调用方可从 CascadeResult 推断
            return False

    def _get_service(self, asset_type: str):
        return {
            "conflict": self.conflict_svc,
            "mystery": self.mystery_svc,
            "twist": self.twist_svc,
            "promise": self.promise_svc,
            "reveal": self.reveal_svc,
            "expectation": self.expectation_svc,
            "goal": self.goal_svc,
            "foreshadowing": self.foreshadowing_svc,
        }.get(asset_type)