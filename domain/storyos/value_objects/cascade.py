"""CascadeStep（spec §3.2 单步级联动作）。"""
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
