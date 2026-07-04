"""Tests for ScenePlan dataclass (StoryOS 1C Task A1, spec §3.1)."""
from __future__ import annotations

import pytest

from engine.pipeline.beat_contracts import ScenePlan
from domain.storyos.value_objects.predeclared import (
    PredeclaredChange,
    PredeclaredChanges,
)
from domain.storyos.contracts import SFLogType


def test_scene_plan_minimal():
    """ScenePlan 最小构造：仅 chapter_id + outline"""
    plan = ScenePlan(chapter_id=5, outline="本章主角踏入禁地")
    assert plan.chapter_id == 5
    assert plan.outline == "本章主角踏入禁地"
    assert plan.predeclared_changes == PredeclaredChanges()
    assert plan.beats == []


def test_scene_plan_with_predeclared_changes():
    """ScenePlan.predeclared_changes 字段（spec §3.1 ⚡ 锁定）"""
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery", asset_id="m1",
        ),
        PredeclaredChange(
            log_type=SFLogType.CONFLICT_ESCALATE,
            asset_type="conflict", asset_id="c1",
        ),
    ])
    plan = ScenePlan(
        chapter_id=5,
        outline="",
        predeclared_changes=predeclared,
    )
    assert plan.predeclared_changes is predeclared
    assert len(plan.predeclared_changes) == 2


def test_scene_plan_to_shared_state_dict():
    """ScenePlan.to_shared_state_dict 序列化（供 checkpoint / BFF API 使用）"""
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery", asset_id="m1",
        ),
    ])
    plan = ScenePlan(
        chapter_id=5,
        outline="outline text",
        predeclared_changes=predeclared,
    )
    state = plan.to_shared_state_dict()
    assert state["chapter_id"] == 5
    assert state["outline"] == "outline text"
    assert state["predeclared_changes"] == [
        {
            "log_type": "mystery_clue",
            "asset_type": "mystery",
            "asset_id": "m1",
            "asset_pair": None,
            "expected_params": {},
        }
    ]


def test_scene_plan_is_frozen():
    """ScenePlan 不可变（spec §3.2 类似 MatchReport 风格）"""
    from dataclasses import FrozenInstanceError
    plan = ScenePlan(chapter_id=5, outline="")
    with pytest.raises(FrozenInstanceError):
        plan.chapter_id = 6  # type: ignore[misc]