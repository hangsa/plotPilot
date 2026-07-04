"""new_foreshadowing_writer —— 新 storyos_foreshadowing_v1 表 INSERT 抽象。

通过 WriteDispatch.enqueue_txn_batch 走单写者单事务（1A 已扩展）。
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import List, Optional

from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingRecord,
)
from domain.storyos.contracts import AssetStatus
from infrastructure.persistence.database.write_dispatch import enqueue_txn_batch

logger = logging.getLogger(__name__)


class NewForeshadowingWriter:
    """把 LegacyForeshadowingRecord + new_status 写入 storyos_foreshadowing_v1。"""

    _INSERT_SQL = (
        "INSERT OR IGNORE INTO storyos_foreshadowing_v1 "
        "(id, project_id, asset_type, status, description, "
        " importance, planted_chapter, payoff_chapter, resolved_chapter, "
        " migrated_from_legacy_id, created_at) "
        "VALUES (?, ?, 'foreshadowing', ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    def insert_batch(
        self,
        records: List[LegacyForeshadowingRecord],
        statuses: List[AssetStatus],
    ) -> None:
        """批量 INSERT（单事务，WriteDispatch 串行）。"""
        if len(records) != len(statuses):
            raise ValueError("records and statuses length mismatch")
        operations = []
        for rec, new_status in zip(records, statuses):
            operations.append((
                self._INSERT_SQL,
                (
                    f"mig-{rec.id}",  # 新表 ID 加 mig- 前缀避免与未来手建冲突
                    rec.novel_id,
                    new_status.value,
                    rec.description,
                    rec.importance,
                    rec.planted_chapter,
                    rec.due_chapter,
                    rec.resolved_chapter,
                    rec.id,  # migrated_from_legacy_id
                    "2026-07-03T10:00:00",  # created_at（占位，实际由 clock 注入）
                ),
            ))
        enqueue_txn_batch(operations)

    def delete_by_migrated_ids(self, old_ids: List[str]) -> int:
        """根据 old_id 列表删除（rollback 用）。"""
        if not old_ids:
            return 0
        placeholders = ",".join("?" for _ in old_ids)
        sql = (
            f"DELETE FROM storyos_foreshadowing_v1 "
            f"WHERE migrated_from_legacy_id IN ({placeholders})"
        )
        enqueue_txn_batch([(sql, tuple(old_ids))])
        return len(old_ids)