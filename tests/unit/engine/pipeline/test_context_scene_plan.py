"""Tests for PipelineContext.scene_plan field (StoryOS 1C Task A2)."""
from __future__ import annotations

import dataclasses

from engine.pipeline.context import PipelineContext
from engine.pipeline.beat_contracts import ScenePlan
from domain.storyos.value_objects.predeclared import PredeclaredChanges


def test_context_default_scene_plan_is_none():
    """PipelineContext 默认 scene_plan = None（不破坏现有管线）"""
    ctx = PipelineContext(novel_id="n1", chapter_number=5)
    assert ctx.scene_plan is None


def test_context_scene_plan_is_a_declared_field():
    """scene_plan 必须是 dataclass 声明字段（默认 None），不能用 setattr 临时挂上"""
    field_names = {f.name for f in dataclasses.fields(PipelineContext)}
    assert "scene_plan" in field_names

    ctx = PipelineContext(novel_id="n1", chapter_number=5)
    plan = ScenePlan(
        chapter_id=5,
        outline="outline",
        predeclared_changes=PredeclaredChanges(),
    )
    ctx.scene_plan = plan
    assert ctx.scene_plan is plan
    assert ctx.scene_plan.chapter_id == 5
