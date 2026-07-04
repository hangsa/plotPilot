"""StoryOSDelegate — 引擎接入点（spec §3.1 锁定 3 方法合一）。

spec §2.3 钩子映射：
- Step 1 (context-load) → load_active_assets_for_context
- Step 3 (pre-write gate) → validate_predeclared_changes
- Step 5-6 (post-write gate + apply-state) → apply_post_write_results

降级策略：所有方法失败时返回安全的空值，由 PipelineRunner 负责记录到
ctx.storyos_failed 列表，spec §4.3 失败模式 F。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.circuit_breaker_integration import (
    SFLogComplianceGate, ComplianceDecision,
)
from application.storyos.services.evolution_bridge_service import (
    EvolutionBridgeService, EvolutionBridgeError,
)
from application.storyos.services.predeclared_validation import (
    PredeclaredIssue, PredeclaredIssueType, PredeclaredValidation,
)
from application.storyos.services.sf_log_parser_service import SFLogParserService
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext
from application.storyos.value_objects.bridge_result import BridgeResult
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.predeclared import PredeclaredChange, PredeclaredChanges

logger = logging.getLogger(__name__)


class StoryOSDelegate:
    """StoryOS 引擎接入点（spec §3.1）"""

    def __init__(
        self,
        active_assets_service: Any = None,
        parser_service: SFLogParserService | None = None,
        bridge_service: EvolutionBridgeService | None = None,
        compliance_gate: SFLogComplianceGate | None = None,
        cascade_service: CascadeService | None = None,
        registry_services: Optional[dict] = None,  # 1C B2 新增
    ) -> None:
        self.active_assets_service = active_assets_service
        self.parser_service = parser_service
        self.bridge_service = bridge_service
        self.compliance_gate = compliance_gate
        self.cascade_service = cascade_service
        # 保留 None 语义：未配置 vs 已配置但为空 dict
        # - None → validate 跳过（DEGRADED）
        # - {} → 已配置但无服务（每个 asset_type 都被报 DEGRADED）
        self.registry_services = registry_services

    def load_active_assets_for_context(
        self,
        novel_id: str,
        chapter_id: int,
    ) -> ActiveAssetsContext:
        """Step 1 钩子：返回当前章节活跃资产摘要供 LLM context 使用。

        spec §4.1 Step 1：
            Runner->>Delegate: load_active_assets_for_context(novel_id, 5)
            Delegate-->>Runner: ActiveAssetsContext (4 conflicts, 2 mysteries, 1 expectation)
        """
        if self.active_assets_service is None:
            logger.debug("[storyos] active_assets_service 未注入，返回空 context")
            return ActiveAssetsContext(novel_id=novel_id, chapter_id=chapter_id)
        try:
            return self.active_assets_service.build_context(novel_id, chapter_id)
        except Exception as e:
            logger.warning(
                "[storyos] load_active_assets_for_context 失败，降级返回空 context: %s", e,
            )
            return ActiveAssetsContext(novel_id=novel_id, chapter_id=chapter_id)

    def validate_predeclared_changes(
        self,
        novel_id: str,
        chapter_id: int,
        predeclared: PredeclaredChanges,
    ) -> PredeclaredValidation:
        """Step 3 钩子：校验 predeclared_changes 引用的 asset 是否存在。

        spec §4.1 Step 3：
            Runner->>Delegate: validate_predeclared_changes(novel_id, 5, predeclared)
            Delegate-->>Runner: PredeclaredValidation(valid=True)

        实现（spec §4.3 B + 1B GenericRegistryService 锁定）：
        1. 对每个 PredeclaredChange，按 asset_type 查 registry_services[asset_type]
        2. asset_id 存在 → OK；不存在（KeyError）→ ORPHAN_ASSET issue
        3. asset_pair 形式 → 两个 asset_id 都查，任一缺失 → ORPHAN_ASSET
        4. cascade_service 是可选的额外校验（深度/循环），不在 1C 必填范围

        降级（spec §4.3 F）：
        - registry_services 未注入 → valid=True + DEGRADED issue
        - asset_type 不在 registry_services 中 → valid=True + DEGRADED issue
        - registry.get 抛非 KeyError 异常 → 降级 valid=True + DEGRADED issue
        """
        if self.registry_services is None:
            logger.debug("[storyos] registry_services 未注入，validate 跳过")
            return PredeclaredValidation(
                valid=True,
                issues=[
                    PredeclaredIssue(
                        type=PredeclaredIssueType.DEGRADED,
                        message="registry_services 未注入，跳过 asset 存在性校验",
                    ),
                ],
            )

        issues = []
        try:
            for p in predeclared:
                svc = self.registry_services.get(p.asset_type)
                if svc is None:
                    # asset_type 不在配置中 → 跳过（不阻断）
                    issues.append(PredeclaredIssue(
                        type=PredeclaredIssueType.DEGRADED,
                        asset_id=p.asset_id,
                        message=f"asset_type {p.asset_type!r} 无对应 registry，跳过校验",
                    ))
                    continue

                # 1A PredeclaredChange XOR: asset_id XOR asset_pair
                asset_ids_to_check = []
                if p.asset_id is not None:
                    asset_ids_to_check.append(p.asset_id)
                if p.asset_pair is not None:
                    asset_ids_to_check.extend(p.asset_pair)

                for aid in asset_ids_to_check:
                    try:
                        svc.get(aid)
                    except KeyError:
                        issues.append(PredeclaredIssue(
                            type=PredeclaredIssueType.ORPHAN_ASSET,
                            asset_id=aid,
                            message=f"asset {aid!r} not found in {p.asset_type} registry",
                        ))
                    except Exception as e:
                        logger.warning(
                            "[storyos] registry_services[%r].get(%r) 失败: %s",
                            p.asset_type, aid, e,
                        )
                        issues.append(PredeclaredIssue(
                            type=PredeclaredIssueType.DEGRADED,
                            asset_id=aid,
                            message=f"registry 异常: {e}",
                        ))

        except Exception as e:
            logger.warning(
                "[storyos] validate_predeclared_changes 失败，降级 valid=True: %s", e,
            )
            return PredeclaredValidation(
                valid=True,
                issues=[
                    PredeclaredIssue(
                        type=PredeclaredIssueType.DEGRADED,
                        message=f"validate_predeclared_changes 异常: {e}",
                    ),
                ],
            )

        # 过滤掉 DEGRADED 后判断 valid（DEGRADED 不阻断，只记录）
        blocking_issues = [
            i for i in issues
            if i.type != PredeclaredIssueType.DEGRADED
        ]
        return PredeclaredValidation(
            valid=len(blocking_issues) == 0,
            issues=issues,
        )

    # B3 任务占位
    def apply_post_write_results(self, *args, **kwargs):  # placeholder
        raise NotImplementedError("Phase 1C Task B3")