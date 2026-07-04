"""ActiveAssetsContext — Step 1 输入 LLM 的活跃资产摘要（spec §3.1）。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ActiveAssetsContext(BaseModel):
    """当前章节活跃的 narrative asset 摘要。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    novel_id: str
    chapter_id: int

    conflicts: list[dict] = Field(default_factory=list)
    mysteries: list[dict] = Field(default_factory=list)
    twists: list[dict] = Field(default_factory=list)
    promises: list[dict] = Field(default_factory=list)
    reveals: list[dict] = Field(default_factory=list)
    expectations: list[dict] = Field(default_factory=list)
    goals: list[dict] = Field(default_factory=list)
    foreshadowings: list[dict] = Field(default_factory=list)

    @computed_field
    @property
    def total_active(self) -> int:
        return sum(len(getattr(self, field)) for field in [
            "conflicts", "mysteries", "twists", "promises", "reveals",
            "expectations", "goals", "foreshadowings",
        ])
