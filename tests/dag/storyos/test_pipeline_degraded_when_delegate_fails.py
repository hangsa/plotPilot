"""Pipeline 降级集成测试 — 4 个 hook 全部失败时 pipeline 仍能继续（spec §4.3 F）。"""
from unittest.mock import MagicMock
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate


class TestPipelineDegraded:
    def test_all_4_hooks_degrade_gracefully(self):
        """spec §4.3 F: 4 个 hook 全部失败时 pipeline 仍能继续（不抛异常）"""
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.load_active_assets_for_context.side_effect = RuntimeError("step1")
        delegate.validate_predeclared_changes.side_effect = RuntimeError("step3")
        delegate.apply_post_write_results.side_effect = RuntimeError("step6")
        ctx.storyos_delegate = delegate

        from domain.storyos.value_objects.predeclared import PredeclaredChanges

        # 4 个 hook 全部调用
        pipeline._hook_step1_context_load(ctx)
        pipeline._hook_step3_pre_write_gate(ctx, PredeclaredChanges())
        pipeline._hook_step5_post_write_gate(ctx, "text", PredeclaredChanges())
        pipeline._hook_step6_apply_state(ctx, "text", PredeclaredChanges())

        # 全部降级到 failed 列表
        # step1/step3/step6 应该都被记录（step5 因为 spec 配置了 parser_service 但没有 mock 失败，
        # 会走到正常路径或因 MagicMock 默认属性抛错，被 except 捕获，记录到 failed）
        failed_text = " ".join(ctx.storyos_failed)
        assert "step1_context_load" in failed_text
        assert "step3_pre_write_gate" in failed_text
        assert "step6_apply_state" in failed_text

    def test_no_delegate_does_not_crash(self):
        """spec §4.3 F: delegate 未注入时不抛异常（仅记录到 failed 列表）"""
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        from domain.storyos.value_objects.predeclared import PredeclaredChanges

        pipeline._hook_step1_context_load(ctx)
        pipeline._hook_step3_pre_write_gate(ctx, PredeclaredChanges())
        pipeline._hook_step5_post_write_gate(ctx, "text", PredeclaredChanges())
        pipeline._hook_step6_apply_state(ctx, "text", PredeclaredChanges())

        # 4 个 hook 都因为 delegate 未配置，记录到 failed 列表
        assert len(ctx.storyos_failed) == 4
        failed_text = " ".join(ctx.storyos_failed)
        assert "step1_context_load" in failed_text
        assert "step3_pre_write_gate" in failed_text
        assert "step5_post_write_gate" in failed_text
        assert "step6_apply_state" in failed_text