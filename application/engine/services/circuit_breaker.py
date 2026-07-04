"""熔断器：防止 API 雪崩导致所有小说同时进入 ERROR"""
import time
import logging
from enum import Enum
from threading import Lock

logger = logging.getLogger(__name__)


class BreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,    # 连续失败 5 次后断开
        reset_timeout: int = 120,       # 断开后 120 秒尝试恢复
        half_open_max_calls: int = 1,  # 试探阶段最多放行 1 次
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._lock = Lock()

    def is_open(self) -> bool:
        with self._lock:
            if self._state == BreakerState.OPEN:
                if time.time() - self._last_failure_time > self.reset_timeout:
                    logger.info("[CircuitBreaker] → HALF_OPEN，开始试探")
                    self._state = BreakerState.HALF_OPEN
                    self._success_count = 0
                    return False  # 放行试探
                return True  # 仍在断开期
            return False

    def wait_seconds(self) -> float:
        """还需等待多少秒"""
        elapsed = time.time() - self._last_failure_time
        return max(0.0, self.reset_timeout - elapsed)

    def record_success(self):
        with self._lock:
            if self._state == BreakerState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    logger.info("[CircuitBreaker] → CLOSED，恢复正常")
                    self._state = BreakerState.CLOSED
                    self._failure_count = 0
            elif self._state == BreakerState.CLOSED:
                self._failure_count = 0  # 成功重置计数

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._state == BreakerState.HALF_OPEN:
                logger.warning("[CircuitBreaker] 试探失败 → OPEN")
                self._state = BreakerState.OPEN
            elif self._failure_count >= self.failure_threshold:
                logger.warning(
                    f"[CircuitBreaker] 连续失败 {self._failure_count} 次 → OPEN，"
                    f"暂停 {self.reset_timeout}s"
                )
                self._state = BreakerState.OPEN

    @property
    def state(self) -> str:
        return self._state.value


# spec §3.6 锁定的多 gate 扩展
# 签名：record_retry(scope_id, gate, hints, success=False)
#       record_force_pass(scope_id, gate, notes)
#       get_retry_count(scope_id, gate='default') -> int
#       get_retry_hints(scope_id, gate='default') -> list[str]
#       is_gate_open(scope_id, gate='default') -> bool
#       was_force_passed(scope_id, gate='default') -> bool

# 在重新绑定前捕获原始 CircuitBreaker 引用，避免 mixin 在 class 创建时
# 引用到“已替换”的版本。
_OriginalCircuitBreaker = CircuitBreaker


class _MultiGateMixin:
    """多 gate 维度跟踪（spec §3.6 锁定）。

    状态元组：(state, count, last_time, hints, force_passed)
    key = (scope_id, gate)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # key=(scope_id, gate), value=(state, count, last_time, hints, force_passed)
        self._gate_states: dict = {}

    def get_retry_count(self, scope_id, gate: str = "default") -> int:
        with self._lock:
            entry = self._gate_states.get((scope_id, gate))
            return entry[1] if entry else 0

    def get_retry_hints(self, scope_id, gate: str = "default") -> list[str]:
        with self._lock:
            entry = self._gate_states.get((scope_id, gate))
            return list(entry[3]) if entry else []

    def record_retry(
        self, scope_id, gate: str, hints: str = "",
        success: bool = False,
    ) -> None:
        """spec §3.6 锁定：scope_id 在前，gate 在后；hints 累积；success=True 重置。"""
        with self._lock:
            key = (scope_id, gate)
            entry = self._gate_states.get(
                key, (BreakerState.CLOSED, 0, 0.0, [], False)
            )
            state, count, last_time, hint_list, force_passed = entry
            if success:
                count = 0
                state = BreakerState.CLOSED
                hint_list = []  # 成功也清空 hints
            else:
                count += 1
                last_time = time.time()
                if hints:
                    hint_list.append(hints)
                if count >= self.failure_threshold:
                    state = BreakerState.OPEN
            self._gate_states[key] = (
                state, count, last_time, hint_list, force_passed
            )

    def record_force_pass(self, scope_id, gate: str, notes: str) -> None:
        """spec §3.6 锁定：force_pass 后重置 retry_count，标记 was_force_passed。"""
        with self._lock:
            key = (scope_id, gate)
            self._gate_states[key] = (
                BreakerState.CLOSED, 0, 0.0,
                [notes] if notes else [], True,
            )

    def is_gate_open(self, scope_id, gate: str = "default") -> bool:
        with self._lock:
            entry = self._gate_states.get((scope_id, gate))
            if entry is None:
                return False
            state, _, last_time, _, _ = entry
            if state == BreakerState.OPEN:
                if time.time() - last_time > self.reset_timeout:
                    # 重置为 HALF_OPEN
                    new_state = BreakerState.HALF_OPEN
                    self._gate_states[
                        (scope_id, gate)
                    ] = (new_state, 0, last_time, [], False)
                    return False
                return True
            return False

    def was_force_passed(self, scope_id, gate: str = "default") -> bool:
        with self._lock:
            entry = self._gate_states.get((scope_id, gate))
            return entry[4] if entry else False


# 重新绑定 CircuitBreaker 为多 gate 版本（向后兼容，因为旧方法保持）
CircuitBreaker = type(
    "CircuitBreaker",
    (_MultiGateMixin, _OriginalCircuitBreaker),
    {},
)
