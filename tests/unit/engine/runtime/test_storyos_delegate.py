"""StoryOSDelegate 测试 — Step 1 + Step 3 钩子 (spec §3.1)。"""
from unittest.mock import MagicMock

from engine.runtime.storyos_delegate import StoryOSDelegate
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext
from application.storyos.services.predeclared_validation import (
    PredeclaredIssueType, PredeclaredValidation,
)
from domain.storyos.value_objects.predeclared import (
    PredeclaredChange, PredeclaredChanges,
)
from domain.storyos.contracts import SFLogType


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


# ---------------------------------------------------------------------------
# Step 3 钩子测试 — validate_predeclared_changes (spec §3.1)
# ---------------------------------------------------------------------------


def test_validate_predeclared_changes_returns_valid_when_all_assets_exist():
    """Step 3 钩子: 所有 predeclared asset_id 在 registry 中存在时 valid=True

    设计：B2 通过 registry_services.get(asset_type).get(asset_id) 检查存在性
    （1B GenericRegistryService.get 抛 KeyError 表示不存在）。
    cascade_service 用于额外的 cascade 深度/循环校验。
    """
    mystery_svc = MagicMock()
    mystery_svc.get.return_value = MagicMock(id="m1")  # 存在

    delegate = StoryOSDelegate(registry_services={"mystery": mystery_svc})
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery", asset_id="m1",
        ),
    ])
    result = delegate.validate_predeclared_changes("n1", 5, predeclared)
    assert isinstance(result, PredeclaredValidation)
    assert result.valid is True
    assert result.issues == []
    mystery_svc.get.assert_called_once_with("m1")


def test_validate_predeclared_changes_returns_invalid_when_asset_not_found():
    """Step 3 钩子: asset_id 在 registry 中不存在时 valid=False（orphan）"""
    mystery_svc = MagicMock()
    mystery_svc.get.side_effect = KeyError("m1")

    delegate = StoryOSDelegate(registry_services={"mystery": mystery_svc})
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery", asset_id="m1",
        ),
    ])
    result = delegate.validate_predeclared_changes("n1", 5, predeclared)
    assert result.valid is False
    assert len(result.issues) == 1
    assert result.issues[0].type == PredeclaredIssueType.ORPHAN_ASSET
    assert result.issues[0].asset_id == "m1"


def test_validate_predeclared_changes_handles_asset_pair():
    """Step 3 钩子: asset_pair 形式（CHARACTER_RELATION_CHANGE）的 predeclared
    需要检查两个 asset 都存在。
    """
    character_svc = MagicMock()
    # c1 返回 OK；c2 未配置返回（MagicMock 默认 .get 返回 MagicMock，不会抛 KeyError）
    # 因此需要 side_effect 来精确模拟 c1 存在 / c2 不存在
    character_svc.get.side_effect = lambda aid: MagicMock(id=aid) if aid == "c1" else (_ for _ in ()).throw(KeyError(aid))

    delegate = StoryOSDelegate(registry_services={"character": character_svc})
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.CHARACTER_RELATION_CHANGE,
            asset_type="character",
            asset_pair=("c1", "c2"),  # 两个角色
        ),
    ])
    result = delegate.validate_predeclared_changes("n1", 5, predeclared)
    # c1 存在，c2 缺失 → valid=False
    assert result.valid is False
    assert any(i.asset_id == "c2" for i in result.issues)
    # c1.get 调一次，c2.get 调一次（两次查询）
    assert character_svc.get.call_count == 2


def test_validate_predeclared_changes_returns_valid_when_registries_none():
    """降级: registry_services 未注入时返回 valid=True + issues 记录降级原因"""
    delegate = StoryOSDelegate(registry_services=None)
    predeclared = PredeclaredChanges()
    result = delegate.validate_predeclared_changes("n1", 5, predeclared)
    assert result.valid is True
    assert any("registry_services 未注入" in issue.message for issue in result.issues)


def test_validate_predeclared_changes_returns_valid_when_asset_type_not_in_registries():
    """降级: predeclared 的 asset_type 不在 registry_services 中时（未配置）跳过检查"""
    delegate = StoryOSDelegate(registry_services={})  # 空 dict
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery", asset_id="m1",
        ),
    ])
    result = delegate.validate_predeclared_changes("n1", 5, predeclared)
    # mystery registry 未配置 → valid=True（不阻断）
    assert result.valid is True
    assert any("mystery" in issue.message for issue in result.issues)