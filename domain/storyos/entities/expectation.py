"""Expectation 实体（读者预期，cascade 修改 intensity）。"""
from __future__ import annotations

from dataclasses import dataclass, replace

from domain.storyos.contracts import AssetStatus


@dataclass(frozen=True)
class Expectation:
    """读者对剧情的预期。"""

    id: str
    novel_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    intensity: int

    def __post_init__(self):
        if self.created_chapter < 1:
            raise ValueError("created_chapter must be >= 1")
        if not 0 <= self.intensity <= 100:
            raise ValueError(f"intensity must be in [0, 100], got {self.intensity}")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")

    def intensify(self, delta: int) -> "Expectation":
        """调整 intensity，自动 clamp 到 [0, 100]。"""
        new_intensity = max(0, min(100, self.intensity + delta))
        return replace(self, intensity=new_intensity)