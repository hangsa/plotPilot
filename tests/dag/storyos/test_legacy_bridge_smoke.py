"""StoryOS tier_0 — legacy 写作路径桥接 smoke 测试。

PLOTPILOT_USE_STORY_PIPELINE=off 时走 legacy_writing_delegate 路径；
章节落盘后应触发 host.storyos_delegate.apply_post_write_results
（spec §2.3 Step 5/6 在 legacy 路径下的最小等价）。
"""
import asyncio
from unittest.mock import MagicMock

from application.storyos.value_objects.bridge_result import BridgeResult
from domain.storyos.value_objects.predeclared import PredeclaredChanges
from engine.runtime.legacy_writing_delegate import _post_chapter_storyos_bridge


def test_legacy_post_chapter_bridge_invokes_delegate():
    """legacy 写作路径应在章节落盘后调用 storyos_delegate.apply_post_write_results。"""
    expected = BridgeResult(
        bridge_id="b-legacy-1",
        chapter_id=5,
        transaction_id="tx-1",
        success=True,
        evolution_actions_applied=1,
        sflog_events_recorded=1,
    )
    delegate = MagicMock()
    delegate.apply_post_write_results.return_value = expected

    host = MagicMock()
    host.storyos_delegate = delegate

    asyncio.run(_post_chapter_storyos_bridge(
        host, "n-1", 5,
        'A <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="blood" --> B',
    ))

    delegate.apply_post_write_results.assert_called_once()
    _args, kwargs = delegate.apply_post_write_results.call_args
    assert kwargs["novel_id"] == "n-1"
    assert kwargs["chapter_id"] == 5
    assert "SF_LOG MYSTERY_CLUE" in kwargs["text"]
    assert isinstance(kwargs["predeclared"], PredeclaredChanges)


def test_legacy_bridge_graceful_when_delegate_missing():
    """host.storyos_delegate 为 None 时降级返回，不抛异常。"""
    host = MagicMock(spec=[])  # spec=[] 强制 MagicMock 不创建任何属性
    # 不抛异常 = 通过
    asyncio.run(_post_chapter_storyos_bridge(host, "n-1", 5, "正文"))


def test_legacy_bridge_logs_warning_on_failure_but_does_not_raise():
    """delegate 抛异常时降级 log warning，主流程不受影响。"""
    delegate = MagicMock()
    delegate.apply_post_write_results.side_effect = RuntimeError("bridge boom")

    host = MagicMock()
    host.storyos_delegate = delegate

    # 不抛异常 = 通过
    asyncio.run(_post_chapter_storyos_bridge(
        host, "n-1", 5, '<!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="x" -->',
    ))
