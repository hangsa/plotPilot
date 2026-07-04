"""CascadeService — BFS 级联执行（spec §4.2 锁定 MAX_DEPTH=3）。"""
from __future__ import annotations

from domain.storyos.contracts import AssetStatus
from domain.storyos.value_objects.cascade import CascadeResult, CascadeRules, CascadeStep
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService


class CascadeService:
    def __init__(
        self,
        conflict_svc: ConflictRegistryService | None = None,
        expectation_svc: ExpectationRegistryService | None = None,
        max_depth: int = 3,
    ) -> None:
        self.conflict_svc = conflict_svc
        self.expectation_svc = expectation_svc
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
            self._apply_step(step)
            result.steps_executed.append(step)
        return result.model_copy(update={"max_depth_reached": len(visited)})

    def _apply_step(self, step: CascadeStep) -> None:
        if step.intensity_delta is not None and self.expectation_svc is not None:
            try:
                self.expectation_svc.intensify(step.target_asset_id, step.intensity_delta)
            except KeyError:
                pass
        if step.new_status is not None and self.conflict_svc is not None:
            try:
                self.conflict_svc.update(step.target_asset_id, status=step.new_status)
            except KeyError:
                pass