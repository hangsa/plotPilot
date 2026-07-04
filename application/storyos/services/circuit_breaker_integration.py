"""SFLogComplianceGate — 4 类决策（spec §4.4 锁定）。

使用 spec §3.6 锁定的 CircuitBreaker 多 gate API：
  - record_retry(scope_id, gate, hints)
  - record_force_pass(scope_id, gate, notes)
  - get_retry_count(scope_id, gate)
  - is_gate_open(scope_id, gate)
"""
from __future__ import annotations

from enum import Enum

from application.engine.services.circuit_breaker import CircuitBreaker
from domain.storyos.value_objects.predeclared import PredeclaredChanges
from domain.storyos.value_objects.sf_log import SFLogRecord


class ComplianceDecision(str, Enum):
    PASS = "pass"
    WARN = "warn"                  # spec §4.4: WARN_AND_PASS
    RETRY = "retry"
    FORCE_PASS = "force_pass"      # spec §4.4: 触发条件 retry_count >= 3


class SFLogComplianceGate:
    """根据 predeclared vs 实际 records 的差异决策（spec §4.4）。"""

    GATE = "sflog_compliance"
    MAX_RETRIES = 4  # threshold for FORCE_PASS; 4th retry triggers (spec §4.4: retry_count >= MAX_RETRIES)

    def __init__(self, circuit_breaker: CircuitBreaker) -> None:
        self._cb = circuit_breaker

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """暴露 CB 供 bridge 失败时调 record_force_pass。"""
        return self._cb

    def evaluate(
        self,
        predeclared: PredeclaredChanges,
        records: list[SFLogRecord],
        scope_id: int | str,
    ) -> ComplianceDecision:
        predeclared_ids = {p.asset_id for p in predeclared if p.asset_id}
        actual_ids = {r.asset_id for r in records if r.asset_id}

        missing = predeclared_ids - actual_ids
        unexpected = actual_ids - predeclared_ids

        if not missing and not unexpected:
            self._cb.record_retry(scope_id, self.GATE, hints="", success=True)
            return ComplianceDecision.PASS

        if missing and not unexpected:
            # spec §4.4：缺 → RETRY（带 hint）→ 阈值后 FORCE_PASS
            hints_text = f"missing {sorted(missing)}"
            self._cb.record_retry(scope_id, self.GATE, hints=hints_text)
            retry_count = self._cb.get_retry_count(scope_id, self.GATE)
            if retry_count >= self.MAX_RETRIES:
                # spec §3.6 锁定 record_force_pass(scope_id, gate, notes)
                self._cb.record_force_pass(
                    scope_id, self.GATE,
                    notes=f"max retries {self.MAX_RETRIES} reached; force passing",
                )
                return ComplianceDecision.FORCE_PASS
            return ComplianceDecision.RETRY

        # unexpected → WARN（spec §4.4 WARN_AND_PASS 决策）
        self._cb.record_retry(scope_id, self.GATE, hints="", success=True)
        return ComplianceDecision.WARN