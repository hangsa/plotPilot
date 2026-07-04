"""CascadePreview — 1D 前端 dry-run 展示用。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus
from domain.storyos.value_objects.cascade import CascadeStep


class CascadePreview(BaseModel):
    """simulate() 的返回值：预测级联结果，不实际应用。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step: CascadeStep
    would_block: bool
    block_reason: str | None = None
    predicted_new_status: AssetStatus | None = None
    predicted_intensity: int | None = None
