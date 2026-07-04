"""review-1c I1: _step_finalize 必须把 ctx.storyos_failed 落到 audit_snapshot。

1D BFF / StoryOSHub 失败面板以此为数据源（plan §5.2 + §6.4）。
"""
import asyncio

from engine.pipeline.base import BaseStoryPipeline
from engine.pipeline.context import PipelineContext


def test_finalize_includes_storyos_failures_in_audit_snapshot():
    """_step_finalize 构造 audit_snapshot 时写入 ctx.storyos_failed 副本"""
    pipeline = BaseStoryPipeline()
    ctx = PipelineContext(novel_id="n1", chapter_number=5)
    ctx.storyos_failed = ["step1_context_load", "step6_apply_state"]

    asyncio.run(pipeline._step_finalize(ctx))

    assert "storyos_failures" in ctx.audit_snapshot
    assert ctx.audit_snapshot["storyos_failures"] == [
        "step1_context_load", "step6_apply_state",
    ]


def test_finalize_storyos_failures_is_a_copy_not_alias():
    """audit_snapshot 里的 storyos_failures 是 list(ctx.storyos_failed) 副本。

    若 orchestrator finalize 之后 hook 又向 ctx.storyos_failed append，audit_snapshot
    不应被回溯修改（避免 1D 消费侧看到已"冻结"的快照仍在变化）。
    """
    pipeline = BaseStoryPipeline()
    ctx = PipelineContext(novel_id="n1", chapter_number=5)
    ctx.storyos_failed = ["step1_context_load"]

    asyncio.run(pipeline._step_finalize(ctx))

    snapshot_failures = ctx.audit_snapshot["storyos_failures"]
    ctx.storyos_failed.append("step6_apply_state")
    assert snapshot_failures == ["step1_context_load"]


def test_finalize_storyos_failures_default_empty_list():
    """ctx.storyos_failed 默认空时，audit_snapshot["storyos_failures"] 也应是 []"""
    pipeline = BaseStoryPipeline()
    ctx = PipelineContext(novel_id="n1", chapter_number=5)

    asyncio.run(pipeline._step_finalize(ctx))

    assert ctx.audit_snapshot.get("storyos_failures") == []