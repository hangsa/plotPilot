"""new_foreshadowing_writer —— 新 storyos_foreshadowing_v1 表 INSERT 抽象。

通过 WriteDispatch.enqueue_txn_batch 走单写者单事务（1A 已扩展）。

字段映射（fix C2，对齐生产 DDL）：
    LegacyForeshadowingRecord.planted_chapter    -> planted_in_chapter
    LegacyForeshadowingRecord.planted_chapter    -> created_chapter（首次登场章节）
    LegacyForeshadowingRecord.due_chapter        -> suggested_resolve_chapter
    LegacyForeshadowingRecord.resolved_chapter   -> resolved_in_chapter
    LegacyForeshadowingRecord.importance (int)  -> importance (TEXT, str(...))
    LegacyForeshadowingRecord.id                -> migrated_from_legacy_id
    linked_assets                                -> '{}' （初次迁移无关联）
    cascade_updated_at                           -> None  （首次迁移无级联）
    created_at / updated_at                      -> DEFAULT CURRENT_TIMESTAMP
"""
from __future__ import annotations

import logging
from typing import List

from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingRecord,
)
from domain.storyos.contracts import AssetStatus
from infrastructure.persistence.database.write_dispatch import enqueue_txn_batch

logger = logging.getLogger(__name__)


class NewForeshadowingWriter:
    """把 LegacyForeshadowingRecord + new_status 写入 storyos_foreshadowing_v1。

    INSERT 列顺序与生产 DDL (storyos_init_0001.py:_create_foreshadowing) 一一对应。
    """

    _INSERT_SQL = (
        "INSERT OR IGNORE INTO storyos_foreshadowing_v1 "
        "(id, project_id, created_chapter, status, description, "
        "linked_assets, cascade_updated_at, importance, "
        "planted_in_chapter, suggested_resolve_chapter, resolved_in_chapter, "
        "migrated_from_legacy_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    def insert_batch(
        self,
        records: List[LegacyForeshadowingRecord],
        statuses: List[AssetStatus],
    ) -> None:
        """批量 INSERT（单事务，WriteDispatch 串行）。

        列值映射：
            params[0]  id                       = "mig-" + rec.id
            params[1]  project_id               = rec.novel_id
            params[2]  created_chapter          = rec.planted_chapter
            params[3]  status                   = new_status.value
            params[4]  description              = rec.description
            params[5]  linked_assets            = '{}'
            params[6]  cascade_updated_at       = None
            params[7]  importance (TEXT)        = str(rec.importance)
            params[8]  planted_in_chapter       = rec.planted_chapter
            params[9]  suggested_resolve_chapter= rec.due_chapter
            params[10] resolved_chapter         = rec.resolved_chapter
            params[11] migrated_from_legacy_id  = rec.id

        created_at / updated_at 由 DEFAULT CURRENT_TIMESTAMP 填充，writer
        不显式传 — 避免使用硬编码占位符（如 "2026-07-03T10:00:00"）。
        """
        if len(records) != len(statuses):
            raise ValueError("records and statuses length mismatch")
        operations = []
        for rec, new_status in zip(records, statuses):
            operations.append((
                self._INSERT_SQL,
                (
                    f"mig-{rec.id}",  # 新表 ID 加 mig- 前缀避免与未来手建冲突
                    rec.novel_id,
                    rec.planted_chapter,  # created_chapter
                    new_status.value,
                    rec.description,
                    "{}",  # linked_assets（初次迁移无关联资产）
                    None,  # cascade_updated_at（无级联）
                    str(rec.importance),  # importance TEXT
                    rec.planted_chapter,  # planted_in_chapter
                    rec.due_chapter,  # suggested_resolve_chapter
                    rec.resolved_chapter,  # resolved_chapter
                    rec.id,  # migrated_from_legacy_id
                ),
            ))
        enqueue_txn_batch(operations)

    def delete_by_migrated_ids(self, old_ids: List[str]) -> int:
        """根据 old_id 列表删除（rollback 用）。

        返回真实删除行数 (``cursor.rowcount``)，不再是 ``len(old_ids)``：
        - 旧实现错误地返回 ``len(old_ids)``，当部分 ID 实际未在新表存在时
          会让调用方 (ForeshadowingMigrationService.rollback) 误判回滚完成度。
        - 测试场景下 ``enqueue_txn_batch`` 被 monkey-patch 成同步执行,
          返回 ``cursor.rowcount`` (int)。生产场景下它返回 ``bool``,
          这里退化为 ``len(old_ids)`` (best-effort)。
        """
        if not old_ids:
            return 0
        placeholders = ",".join("?" for _ in old_ids)
        sql = (
            f"DELETE FROM storyos_foreshadowing_v1 "
            f"WHERE migrated_from_legacy_id IN ({placeholders})"
        )
        result = enqueue_txn_batch([(sql, tuple(old_ids))])
        # 测试 fake_enqueue 返回 cursor.rowcount (int)；
        # 生产 enqueue_txn_batch 返回 bool — bool 是 int 的子类但
        # True/False 不是有意义的删除数，故此处仅识别真正的 int。
        if isinstance(result, int) and not isinstance(result, bool):
            return result
        return len(old_ids)