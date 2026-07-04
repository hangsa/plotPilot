"""ForeshadowingMigrationService — 1B 留 stub，1E 阶段补完业务逻辑。"""
from __future__ import annotations


class ForeshadowingMigrationService:
    """Foreshadowing 单向迁移：旧表 → storyos_foreshadowing_v1。"""

    def scan(self):
        raise NotImplementedError("完整实现在 Phase 1E")

    def execute(self, batch_size: int = 500):
        raise NotImplementedError("完整实现在 Phase 1E")

    def rollback(self, migration_id: str):
        raise NotImplementedError("完整实现在 Phase 1E")