"""Step 3 钩子集成测试 — _hook_step3_pre_write_gate (spec §4.1 Step 3)."""
from unittest.mock import MagicMock
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate
from domain.storyos.value_objects.predeclared import PredeclaredChanges
from application.storyos.services.predeclared_validation import (
    PredeclaredValidation, PredeclaredIssue, PredeclaredIssueType,
)


class TestStep3Hook:
    def test_validate_predeclared_calls_delegate(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        expected = PredeclaredValidation(valid=True, issues=[])
        delegate.validate_predeclared_changes.return_value = expected
        ctx.storyos_delegate = delegate
        predeclared = PredeclaredChanges()

        result = pipeline._hook_step3_pre_write_gate(ctx, predeclared)
        assert result is expected
        assert ctx.storyos_validation is expected
        delegate.validate_predeclared_changes.assert_called_once_with("n1", 5, predeclared)

    def test_step3_hook_degrades_on_delegate_failure(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.validate_predeclared_changes.side_effect = RuntimeError("boom")
        ctx.storyos_delegate = delegate
        predeclared = PredeclaredChanges()

        result = pipeline._hook_step3_pre_write_gate(ctx, predeclared)
        assert result is None
        assert any("step3_pre_write_gate" in s for s in ctx.storyos_failed)