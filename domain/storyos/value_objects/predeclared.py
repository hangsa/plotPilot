"""PredeclaredChange + PredeclaredChanges（spec §3.2 / §4.4）。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from domain.storyos.contracts import SFLogType


class PredeclaredChange(BaseModel):
    """LLM 在生成章节前预声明的 state 变更。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    log_type: SFLogType
    asset_type: str = Field(min_length=1)
    asset_id: str | None = None
    asset_pair: tuple[str, str] | None = None
    expected_params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _xor_id_pair(self) -> PredeclaredChange:
        id_set = self.asset_id is not None
        pair_set = self.asset_pair is not None
        if id_set == pair_set:
            raise ValueError(
                f"PredeclaredChange requires exactly one of asset_id or asset_pair, "
                f"got asset_id={self.asset_id}, asset_pair={self.asset_pair}"
            )
        return self


class PredeclaredChanges(BaseModel):
    """PredeclaredChange 的聚合容器。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[PredeclaredChange] = Field(default_factory=list)

    def __iter__(self):
        return iter(self.items)

    def __contains__(self, item: PredeclaredChange) -> bool:
        return item in self.items

    def __len__(self) -> int:
        return len(self.items)
