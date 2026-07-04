"""Step 1 钩子测试 — load_active_assets_for_context (spec §3.1)。"""
from unittest.mock import MagicMock

from engine.runtime.storyos_delegate import StoryOSDelegate
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext


def test_load_active_assets_for_context_delegates_to_service():
    """Step 1 钩子: delegate.load_active_assets_for_context → ActiveAssetsService.build_context"""
    active_svc = MagicMock()
    expected = ActiveAssetsContext(novel_id="n1", chapter_id=5)
    active_svc.build_context.return_value = expected

    delegate = StoryOSDelegate(active_assets_service=active_svc)
    result = delegate.load_active_assets_for_context("n1", 5)
    assert result is expected
    active_svc.build_context.assert_called_once_with("n1", 5)


def test_load_active_assets_for_context_returns_empty_on_service_none():
    """降级策略: service 未注入时返回空 ActiveAssetsContext（不抛异常）"""
    delegate = StoryOSDelegate(active_assets_service=None)
    result = delegate.load_active_assets_for_context("n1", 5)
    assert result.novel_id == "n1"
    assert result.chapter_id == 5
    assert result.total_active == 0


def test_load_active_assets_for_context_returns_empty_on_service_failure():
    """降级策略: service 抛异常时返回空 ActiveAssetsContext + 记录到 ctx（spec §4.3 F）"""
    active_svc = MagicMock()
    active_svc.build_context.side_effect = RuntimeError("db down")
    delegate = StoryOSDelegate(active_assets_service=active_svc)
    result = delegate.load_active_assets_for_context("n1", 5)
    assert result.novel_id == "n1"
    assert result.chapter_id == 5
    assert result.total_active == 0