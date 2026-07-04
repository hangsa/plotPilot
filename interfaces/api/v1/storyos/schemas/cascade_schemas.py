"""Cascade 端点专用 DTO。"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep


class CascadeStepDTO(BaseModel):
    """CascadeStep 的 API 表示。"""

    model_config = ConfigDict(from_attributes=True)

    trigger: CascadeTrigger
    source_asset_type: str
    source_asset_id: str
    target_asset_type: str
    target_asset_id: str
    new_status: Optional[AssetStatus] = None
    intensity_delta: Optional[int] = None
    reason: str = ""

    @classmethod
    def from_domain(cls, step: CascadeStep) -> "CascadeStepDTO":
        return cls(
            trigger=step.trigger,
            source_asset_type=step.source_asset_type,
            source_asset_id=step.source_asset_id,
            target_asset_type=step.target_asset_type,
            target_asset_id=step.target_asset_id,
            new_status=step.new_status,
            intensity_delta=step.intensity_delta,
            reason=step.reason,
        )


class CascadeSimulateSummary(BaseModel):
    """模拟结果摘要（避免前端遍历 steps 计算）。"""

    model_config = ConfigDict(extra="forbid")

    would_block: bool
    max_depth_reached: int = Field(ge=0)
    steps_count: int = Field(ge=0)
    blocked_steps_count: int = Field(ge=0)
    would_create_cycle: bool = False


class CascadeSimulateRequest(BaseModel):
    """POST /cascade/simulate body。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=64)
    trigger: CascadeTrigger
    source_asset_type: str = Field(min_length=1, max_length=32)
    source_asset_id: str = Field(min_length=1, max_length=128)
    proposed_new_status: Optional[AssetStatus] = None  # 触发的初始状态变更
    max_depth: int = Field(default=3, ge=1, le=3)  # spec §4.2 锁定 3


class CascadeSimulateResponse(BaseModel):
    """POST /cascade/simulate 响应。"""

    model_config = ConfigDict(extra="forbid")

    steps: list[CascadeStepDTO]
    summary: CascadeSimulateSummary
    blocked_steps: list[CascadeStepDTO] = Field(default_factory=list)


class CascadeReplayRequest(BaseModel):
    """POST /cascade/replay/{bridge_id} body。"""

    model_config = ConfigDict(extra="forbid")

    notes: Optional[str] = Field(default=None, max_length=1000)
