"""StoryOSDelegate 测试 — Step 1 + Step 3 + Step 5-6 钩子 (spec §3.1)。"""
from unittest.mock import MagicMock

from engine.runtime.storyos_delegate import StoryOSDelegate
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext
from application.storyos.value_objects.bridge_result import BridgeResult
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


# ---------------------------------------------------------------------------
# Step 5-6 钩子测试 — apply_post_write_results (spec §3.1)
# ---------------------------------------------------------------------------


def test_apply_post_write_results_happy_path():
    """Step 5-6 合并钩子: parse → validate → match → bridge 流水线"""
    parser = MagicMock()
    parser.parse.return_value = [MagicMock(log_type="mystery_clue", asset_id="m1")]
    parser.validate_format.return_value = []  # 无格式错误
    parser.match_against_predeclared.return_value = MagicMock(
        missing_changes=[],
        unexpected_records=[],
        should_retry=False,
    )

    bridge = MagicMock()
    # 1B BridgeResult 14 字段（spec §3.2 锁定）：bridge_id/chapter_id/transaction_id/...
    expected = BridgeResult(
        bridge_id="b1", chapter_id=5, transaction_id="tx1",
        success=True, evolution_actions_applied=3, sflog_events_recorded=1,
    )
    bridge.apply_sflog_batch.return_value = expected

    delegate = StoryOSDelegate(parser_service=parser, bridge_service=bridge)
    predeclared = PredeclaredChanges()
    result = delegate.apply_post_write_results("n1", 5, "text", predeclared)

    assert result is expected
    assert result.success is True
    parser.parse.assert_called_once_with("text", 5)
    bridge.apply_sflog_batch.assert_called_once()


def test_apply_post_write_results_returns_failure_on_format_error():
    """Step 5: 格式错误时返回失败结果（不抛异常，spec §4.3 A）"""
    from domain.storyos.value_objects.format_error import FormatError

    parser = MagicMock()
    parser.parse.return_value = []
    parser.validate_format.return_value = [
        FormatError(code="MALFORMED_TAG", message="bad tag", raw_text="", char_position=10),
    ]

    delegate = StoryOSDelegate(parser_service=parser, bridge_service=MagicMock())
    result = delegate.apply_post_write_results("n1", 5, "text", PredeclaredChanges())
    assert result.success is False
    assert "MALFORMED_TAG" in (result.error or "")


def test_apply_post_write_results_bridge_failure_records_force_pass():
    """Step 6: bridge 失败时调用 compliance_gate.record_force_pass（spec §4.3 D）

    1B ComplianceGate 是通过 circuit_breaker 暴露 record_force_pass，
    delegate 必须走 circuit_breaker.record_force_pass(scope_id, gate, notes)
    """
    from application.storyos.services.evolution_bridge_service import EvolutionBridgeError

    parser = MagicMock()
    parser.parse.return_value = []
    parser.validate_format.return_value = []
    parser.match_against_predeclared.return_value = MagicMock(
        missing_changes=[], unexpected_records=[], should_retry=False,
    )

    bridge = MagicMock()
    bridge.apply_sflog_batch.side_effect = EvolutionBridgeError("SQL constraint")

    gate = MagicMock()
    # 1B SFLogComplianceGate 暴露 circuit_breaker 属性
    cb = MagicMock()
    gate.circuit_breaker = cb
    cb.record_force_pass = MagicMock()

    delegate = StoryOSDelegate(
        parser_service=parser, bridge_service=bridge, compliance_gate=gate,
    )
    result = delegate.apply_post_write_results("n1", 5, "text", PredeclaredChanges())
    assert result.success is False
    cb.record_force_pass.assert_called_once()
    call_args = cb.record_force_pass.call_args
    # 1B record_force_pass(scope_id, gate, notes) 位置参数
    assert call_args.args[0] == "n1:5"  # scope_id
    assert call_args.args[1] == "sflog_compliance"  # gate name (must match EvolutionBridgeService)
    assert "SQL constraint" in call_args.args[2]  # notes


def test_apply_post_write_results_returns_failure_on_parser_exception():
    """降级: parser 抛异常时返回失败 BridgeResult（spec §4.3 F）

    返回的失败 BridgeResult 仍需 14 字段全填，success=False + error=...。
    """
    parser = MagicMock()
    parser.parse.side_effect = RuntimeError("regex catastrophic backtrack")
    delegate = StoryOSDelegate(parser_service=parser, bridge_service=MagicMock())
    result = delegate.apply_post_write_results("n1", 5, "text", PredeclaredChanges())
    assert result.success is False
    assert "regex catastrophic" in (result.error or "")
    # 验证 14 字段都有合法值（即使失败也保留结构）
    assert result.bridge_id  # 由 delegate 生成
    assert result.chapter_id == 5