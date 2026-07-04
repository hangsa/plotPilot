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
from typing import Any

from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.circuit_breaker_integration import (
    SFLogComplianceGate, ComplianceDecision,
)
from application.storyos.services.evolution_bridge_service import (
    EvolutionBridgeService, EvolutionBridgeError,
)
from application.storyos.services.sf_log_parser_service import SFLogParserService
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext
from application.storyos.value_objects.bridge_result import BridgeResult
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.predeclared import PredeclaredChanges

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
        registry_services: dict[str, Any] | None = None,  # 1C B2 新增
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

    # 其他两个方法在 B2 / B3 任务中实现
    def validate_predeclared_changes(self, *args, **kwargs):  # placeholder
        raise NotImplementedError("Phase 1C Task B2")

    def apply_post_write_results(self, *args, **kwargs):  # placeholder
        raise NotImplementedError("Phase 1C Task B3")