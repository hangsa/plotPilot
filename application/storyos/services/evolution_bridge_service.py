"""EvolutionBridgeService — 单事务三操作（spec §4.1 锁定）。

spec §4.1 Step 6 序列图锁定：
    Bridge.apply_sflog_batch(novel_id, 5, records) -> BridgeResult

错误处理（spec §4.3 D 失败模式）：
    1. Evolution reducer 失败 → 单事务 ROLLBACK
    2. 事务外写 bridge_log（spec §3.4 ⚡）
    3. 调 compliance gate record_force_pass → pipeline runner 据此决策 RETRY/FORCE_PASS
"""
from __future__ import annotations

import time
import uuid

from application.engine.services.circuit_breaker import CircuitBreaker
from application.storyos.parsers.sf_log_action_mapper import SFLogActionMapper
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.circuit_breaker_integration import SFLogComplianceGate
from application.storyos.value_objects.bridge_result import BridgeResult
from domain.storyos.value_objects.sf_log import SFLogRecord
from infrastructure.persistence.database.write_dispatch import WriteDispatch


class EvolutionBridgeError(Exception):
    pass


class EvolutionBridgeService:
    def __init__(
        self,
        action_mapper: SFLogActionMapper,
        cascade_service: CascadeService,
        compliance_gate: SFLogComplianceGate | None = None,
    ) -> None:
        self.action_mapper = action_mapper
        self.cascade_service = cascade_service
        self.compliance_gate = compliance_gate

    def apply_sflog_batch(
        self,
        novel_id: str,
        chapter_id: int,
        records: list[SFLogRecord],
        scope_id: str | int | None = None,
    ) -> BridgeResult:
        """spec §4.1 Step 6 锁定方法名。

        Args:
            novel_id: 项目 ID
            chapter_id: 章节号
            records: SFLogRecord 列表
            scope_id: circuit breaker scope（默认用 novel_id）
        """
        bridge_id = str(uuid.uuid4())
        transaction_id = str(uuid.uuid4()) if records else None
        start = time.monotonic()
        scope_id = scope_id if scope_id is not None else novel_id

        actions, skipped_log_types = self.action_mapper.map_records(records)
        cascade_result = self.cascade_service.execute([])  # 1B stub；1C 注入 cascade step 来源

        try:
            with WriteDispatch().transaction() as txn:
                # spec §4.1 锁定三 op 顺序
                txn.queue_apply(self._evolution_apply, list(actions), novel_id)
                txn.queue_apply(self._registry_apply, [], novel_id)
                txn.queue_apply(self._sflog_event_record, list(records), novel_id)
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            # spec §3.4 ⚡：bridge_log 在事务外写（避免 ROLLBACK 一起回滚）
            try:
                self._write_bridge_log(
                    bridge_id=bridge_id, chapter_id=chapter_id, transaction_id=transaction_id,
                    success=False, error=str(e), actions_count=len(actions),
                    registry_count=0, cascade_count=len(cascade_result.steps_executed),
                    duration_ms=duration_ms,
                )
            except Exception:
                # bridge_log 自身失败也不能阻止 EvolutionBridgeError 上抛
                pass
            # spec §4.3 D：通知 pipeline runner 失败（force_pass 决策由 runner 做）
            if self.compliance_gate is not None:
                self.compliance_gate.circuit_breaker.record_force_pass(
                    scope_id=scope_id, gate="sflog_compliance",
                    notes=f"bridge failed: {e}",
                )
            raise EvolutionBridgeError(f"bridge failed: {e}") from e

        duration_ms = int((time.monotonic() - start) * 1000)
        return BridgeResult(
            bridge_id=bridge_id, chapter_id=chapter_id, transaction_id=transaction_id,
            evolution_actions_applied=len(actions),
            evolution_actions_skipped=len(skipped_log_types),
            skipped_log_types=list(skipped_log_types),  # spec 锁定 list[SFLogType]
            registry_updates_applied=0,
            cascade_steps_executed=len(cascade_result.steps_executed),
            cascade_steps_blocked=list(cascade_result.blocked_steps),  # spec 锁定 list[CascadeStep]
            sflog_events_recorded=len(records),
            success=True, warnings=[], duration_ms=duration_ms,
        )

    # 三个 op 的占位实现（1C 引擎钩子阶段注入完整业务）
    def _evolution_apply(self, conn, actions, novel_id):
        """spec §4.1：调 Evolution Reducer 处理 actions。1B stub，1C 注入。"""
        conn.execute("SELECT 1")

    def _registry_apply(self, conn, updates, novel_id):
        """spec §4.1：registry_apply_with_cascade。1B stub，1C 注入。"""
        conn.execute("SELECT 1")

    def _sflog_event_record(self, conn, records, novel_id):
        """spec §4.1：sflog_event_record 入 sflog_event 表。1B stub，1C 注入。"""
        conn.execute("SELECT 1")

    def _write_bridge_log(self, *, bridge_id, chapter_id, transaction_id,
                          success, error, actions_count, registry_count,
                          cascade_count, duration_ms):
        """事务外写 bridge_log（spec §3.4 ⚡ + §4.2 prose 锁定走 WriteDispatch.queue_apply）。

        1A 已建表 storyos_bridge_log_v1；1B 阶段直接拼 INSERT，1C 阶段改为调 mapper。
        """
        def _insert(conn):
            conn.execute(
                "INSERT INTO storyos_bridge_log_v1 "
                "(id, project_id, chapter_id, transaction_id, evolution_actions_count, "
                "registry_updates_count, cascade_steps_count, success, error, duration_ms, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (bridge_id, "", chapter_id, transaction_id or "",
                 actions_count, registry_count, cascade_count,
                 int(bool(success)), error or "", duration_ms),
            )

        WriteDispatch().queue_apply(_insert)