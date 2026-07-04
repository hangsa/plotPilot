"""Step 5 钩子集成测试 — _hook_step5_post_write_gate (spec §4.1 Step 5)."""
from unittest.mock import MagicMock
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate
from domain.storyos.value_objects.predeclared import PredeclaredChanges
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.predeclared import PredeclaredChange


class TestStep5Hook:
    def test_post_write_gate_returns_match_report(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)

        delegate = MagicMock(spec=StoryOSDelegate)
        parser = MagicMock()
        parser.parse.return_value = []
        parser.validate_format.return_value = []
        parser.match_against_predeclared.return_value = MagicMock(
            missing_changes=[], unexpected_records=[], should_retry=False,
        )
        delegate.parser_service = parser
        ctx.storyos_delegate = delegate

        predeclared = PredeclaredChanges(items=[
            PredeclaredChange(log_type=SFLogType.MYSTERY_CLUE, asset_type="mystery", asset_id="m1"),
        ])
        result = pipeline._hook_step5_post_write_gate(ctx, "text", predeclared)
        assert "match_report" in result
        assert "format_errors" in result
        assert result["format_errors"] == []

    def test_step5_hook_degrades_on_parser_failure(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.parser_service = MagicMock()
        delegate.parser_service.parse.side_effect = RuntimeError("boom")
        ctx.storyos_delegate = delegate

        result = pipeline._hook_step5_post_write_gate(ctx, "text", PredeclaredChanges())
        assert result is None
        assert any("step5_post_write_gate" in s for s in ctx.storyos_failed)