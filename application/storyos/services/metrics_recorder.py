"""MetricsRecorder — 包装 StoryOSMetrics 收集（spec §5.2 锁定）。"""
from __future__ import annotations

import time
from contextlib import contextmanager

from application.storyos.value_objects.storyos_metrics import StoryOSMetrics


class MetricsRecorder:
    def __init__(self) -> None:
        self._metrics = StoryOSMetrics()

    def record_sflog(self, count: int) -> None:
        # Pydantic frozen：创建新对象
        object.__setattr__(self, "_metrics", self._metrics.model_copy(
            update={"sflog_count": self._metrics.sflog_count + count}
        ))

    @contextmanager
    def bridge_timer(self):
        start = time.perf_counter()
        yield
        duration_ms = int((time.perf_counter() - start) * 1000)
        object.__setattr__(self, "_metrics", self._metrics.model_copy(
            update={"bridge_duration_ms": duration_ms}
        ))

    def metrics(self) -> StoryOSMetrics:
        return self._metrics