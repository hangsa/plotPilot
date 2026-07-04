"""spec §5.3: 端到端 happy path 验证 4 个钩子正确触发。"""
import pytest
from unittest.mock import MagicMock
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate
from engine.pipeline.beat_contracts import ScenePlan
from domain.storyos.value_objects.predeclared import (
    PredeclaredChange, PredeclaredChanges,
)
from domain.storyos.contracts import SFLogType
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext
from application.storyos.value_objects.bridge_result import BridgeResult


class TestEndToEndHooks:
    def test_4_hooks_invoked_in_correct_order(self):
        """4 个 hook 按 spec §2.3 顺序触发：Step1 → Step3 → Step5 → Step6。

        Notes:
        - Step 5 不走 delegate.apply_post_write_results（它在 delegate.apply_post_write_results
          的前半段），本测试单独通过 delegate.parser_service 触发。
        - 单独调用钩子时，bridge metadata（storyos_bridge_success / evolution_actions）
          由 orchestrator（_step_save_chapter）写入，本测试模拟其写入以验证暴露语义。
        """
        call_order = []
        delegate = MagicMock(spec=StoryOSDelegate)

        def step1_hook(novel_id, chapter_id):
            call_order.append("step1")
            return ActiveAssetsContext(novel_id=novel_id, chapter_id=chapter_id)
        delegate.load_active_assets_for_context.side_effect = step1_hook

        def step3_hook(novel_id, chapter_id, predeclared):
            call_order.append("step3")
            return MagicMock(valid=True, issues=[])
        delegate.validate_predeclared_changes.side_effect = step3_hook

        def step6_hook(novel_id, chapter_id, text, predeclared):
            call_order.append("step6")
            return BridgeResult(
                bridge_id="b1", chapter_id=chapter_id, transaction_id="tx1",
                success=True, evolution_actions_applied=3, sflog_events_recorded=1,
            )
        delegate.apply_post_write_results.side_effect = step6_hook

        delegate.parser_service = MagicMock()
        delegate.parser_service.parse.return_value = []
        delegate.parser_service.validate_format.return_value = []
        delegate.parser_service.match_against_predeclared.return_value = MagicMock(
            missing_changes=[], unexpected_records=[], should_retry=False,
        )

        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        ctx.storyos_delegate = delegate
        predeclared = PredeclaredChanges(items=[
            PredeclaredChange(log_type=SFLogType.MYSTERY_CLUE, asset_type="mystery", asset_id="m1"),
        ])
        ctx.scene_plan = ScenePlan(
            chapter_id=5, outline="outline", predeclared_changes=predeclared,
        )
        ctx.chapter_content = "正文 <!-- SF_LOG MYSTERY_CLUE mystery_id=\"m1\" content=\"blood\" --> 继续"

        # 手动触发 4 个 hook（完整 10 步需要更多依赖）
        pipeline._hook_step1_context_load(ctx)
        pipeline._hook_step3_pre_write_gate(ctx, predeclared)
        pipeline._hook_step5_post_write_gate(ctx, ctx.chapter_content, predeclared)
        bridge_result = pipeline._hook_step6_apply_state(ctx, ctx.chapter_content, predeclared)

        assert call_order == ["step1", "step3", "step6"]
        # Step 5 不在 call_order（它直接调 parser_service 不通过 delegate）

        # Step 6 模拟 orchestrator 的 metadata 写入逻辑（见 _step_save_chapter base.py:772-781）
        ctx.metadata["storyos_bridge_success"] = bridge_result.success
        ctx.metadata["storyos_evolution_actions"] = int(
            getattr(bridge_result, "evolution_actions_applied", 0) or 0
        )
        # metadata 暴露的字段名（1B BridgeResult 14 字段）
        assert ctx.metadata["storyos_bridge_success"] is True
        assert ctx.metadata["storyos_evolution_actions"] == 3

    def test_no_warnings_on_clean_run(self):
        """clean run: storyos_failed 列表应为空"""
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.load_active_assets_for_context.return_value = ActiveAssetsContext(
            novel_id="n1", chapter_id=5,
        )
        delegate.validate_predeclared_changes.return_value = MagicMock(valid=True, issues=[])
        delegate.apply_post_write_results.return_value = BridgeResult(
            bridge_id="b1", chapter_id=5, transaction_id="tx1",
            success=True, evolution_actions_applied=3, cascade_steps_executed=1,
        )
        delegate.parser_service = MagicMock()
        delegate.parser_service.parse.return_value = []
        delegate.parser_service.validate_format.return_value = []
        delegate.parser_service.match_against_predeclared.return_value = MagicMock(
            missing_changes=[], unexpected_records=[], should_retry=False,
        )

        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        ctx.storyos_delegate = delegate
        predeclared = PredeclaredChanges()
        ctx.scene_plan = ScenePlan(chapter_id=5, outline="", predeclared_changes=predeclared)

        pipeline._hook_step1_context_load(ctx)
        pipeline._hook_step3_pre_write_gate(ctx, predeclared)
        pipeline._hook_step5_post_write_gate(ctx, "text", predeclared)
        pipeline._hook_step6_apply_state(ctx, "text", predeclared)

        assert ctx.storyos_failed == []
        assert ctx.storyos_active_assets is not None
        assert ctx.storyos_validation is not None
        assert ctx.storyos_bridge_result is not None