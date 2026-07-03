"""CascadeStep + CascadeResult + CascadeRules（spec §3.2）。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain.storyos.contracts import AssetStatus, CascadeTrigger


class CascadeStep(BaseModel):
    """单步级联动作。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trigger: CascadeTrigger
    source_asset_type: str = Field(min_length=1)
    source_asset_id: str = Field(min_length=1)
    target_asset_type: str = Field(min_length=1)
    target_asset_id: str = Field(min_length=1)
    new_status: AssetStatus | None = None
    intensity_delta: int | None = None
    reason: str = ""

    @model_validator(mode="after")
    def _check_status_or_intensity(self) -> CascadeStep:
        if self.new_status is None and self.intensity_delta is None:
            raise ValueError(
                "CascadeStep requires either new_status or intensity_delta"
            )
        return self


class CascadeResult(BaseModel):
    """单次级联执行结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    steps_executed: list[CascadeStep] = Field(default_factory=list)
    blocked_steps: list[CascadeStep] = Field(default_factory=list)
    max_depth_reached: int = 0


class CascadeRules:
    """级联规则工具（cycle detection + depth check）。"""

    def apply_to(
        self,
        step: CascadeStep,
        visited: set[str],
        max_depth: int,
    ) -> dict:
        """判定一个 CascadeStep 是否可执行。

        副作用：当 step 判定为可执行（既不会成环、也未超 depth）时，将
        ``source_asset_id`` 加入 ``visited``，以便后续步骤做 cycle 判定。

        Returns:
            dict with keys:
                - would_create_cycle: bool
                - depth_exceeded: bool
                - reason: str | None
        """
        if step.target_asset_id in visited:
            return {
                "would_create_cycle": True,
                "depth_exceeded": False,
                "reason": f"target {step.target_asset_id} already visited",
            }
        depth = len(visited)
        if depth >= max_depth:
            return {
                "would_create_cycle": False,
                "depth_exceeded": True,
                "reason": f"depth {depth} >= max_depth {max_depth}",
            }
        visited.add(step.source_asset_id)
        return {
            "would_create_cycle": False,
            "depth_exceeded": False,
            "reason": None,
        }
