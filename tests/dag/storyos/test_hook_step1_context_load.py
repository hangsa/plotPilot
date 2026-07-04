"""Step 1 钩子集成测试 — _hook_step1_context_load (spec §4.1 Step 1)."""
import pytest
from unittest.mock import MagicMock
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext


class TestStep1Hook:
    def test_build_context_calls_load_active_assets(self):
        """Step 1: _step_build_context 调用 delegate.load_active_assets_for_context"""
        delegate = MagicMock(spec=StoryOSDelegate)
        expected = ActiveAssetsContext(
            novel_id="n1", chapter_id=5,
            conflicts=[{"id": "c1"}], mysteries=[{"id": "m1"}],
        )
        delegate.load_active_assets_for_context.return_value = expected

        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        ctx.storyos_delegate = delegate

        # 直接调内部 hook 入口
        result = pipeline._hook_step1_context_load(ctx)
        assert result is expected
        assert ctx.storyos_active_assets is expected
        delegate.load_active_assets_for_context.assert_called_once_with("n1", 5)

    def test_step1_hook_degrades_on_delegate_failure(self):
        """Step 1 降级: delegate 抛异常时记录到 ctx.storyos_failed，不抛异常"""
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.load_active_assets_for_context.side_effect = RuntimeError("boom")

        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        ctx.storyos_delegate = delegate

        result = pipeline._hook_step1_context_load(ctx)
        assert result is None
        assert any("step1_context_load" in s for s in ctx.storyos_failed)