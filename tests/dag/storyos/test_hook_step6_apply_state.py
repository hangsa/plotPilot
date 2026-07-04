"""Step 6 钩子集成测试 — _hook_step6_apply_state (spec §4.1 Step 6)."""
from unittest.mock import MagicMock
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate
from domain.storyos.value_objects.predeclared import PredeclaredChanges
from application.storyos.value_objects.bridge_result import BridgeResult


class TestStep6Hook:
    def test_apply_state_calls_delegate(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        # 1B BridgeResult 14 字段
        expected = BridgeResult(
            bridge_id="b1", chapter_id=5, transaction_id="tx1",
            success=True, evolution_actions_applied=3, cascade_steps_executed=1,
            sflog_events_recorded=2,
        )
        delegate.apply_post_write_results.return_value = expected
        ctx.storyos_delegate = delegate
        predeclared = PredeclaredChanges()

        result = pipeline._hook_step6_apply_state(ctx, "text", predeclared)
        assert result is expected
        assert ctx.storyos_bridge_result is expected
        delegate.apply_post_write_results.assert_called_once_with("n1", 5, "text", predeclared)

    def test_step6_hook_degrades_on_delegate_failure(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.apply_post_write_results.side_effect = RuntimeError("boom")
        ctx.storyos_delegate = delegate

        result = pipeline._hook_step6_apply_state(ctx, "text", PredeclaredChanges())
        assert result is None
        assert any("step6_apply_state" in s for s in ctx.storyos_failed)