"""StoryOS 1C C2 — StoryPipelineRunner DI 装配测试。

验证 spec §3.1：
- StoryPipelineRunner.__init__ 接受 storyos_delegate kwarg
- StoryPipelineRunner._make_context 把 storyos_delegate 注入 ctx（_dependencies）
- 通过 _get_storyos_delegate(ctx) 能从 ctx 读到 delegate
"""
from unittest.mock import MagicMock

from engine.runtime.runner import StoryPipelineRunner
from engine.runtime.storyos_delegate import StoryOSDelegate


def test_runner_accepts_storyos_delegate_in_constructor():
    """runner.__init__ 接受 storyos_delegate 参数（spec §3.1）"""
    delegate = MagicMock(spec=StoryOSDelegate)
    runner = StoryPipelineRunner(storyos_delegate=delegate)
    assert runner.storyos_delegate is delegate


def test_runner_injects_delegate_into_context():
    """_make_context 把 storyos_delegate 注入 ctx（供 4 个 hook 读取）"""
    delegate = MagicMock(spec=StoryOSDelegate)
    runner = StoryPipelineRunner(storyos_delegate=delegate)

    ctx = runner._make_context("n1", 5)
    assert ctx.get_dep("storyos_delegate") is delegate
    # 验证 _step_* 流程能通过 _get_storyos_delegate 找到
    pipeline = StoryPipelineRunner()
    pipeline.storyos_delegate = delegate
    retrieved = pipeline._get_storyos_delegate(ctx)
    assert retrieved is delegate