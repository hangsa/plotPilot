"""ForeshadowingMigrationService —— 旧 foreshadows 表 → storyos_foreshadowing_v1 单向迁移。

3 方法（spec §1E 锁定）：
- scan(project_id) → MigrationPreviewReport：只读扫描，生成 5 元组报告
- execute(project_id, batch_size, dry_run) → MigrationExecuteResult：批量迁移
- rollback(migration_id) → RollbackResult：基于 migration_log 回滚单条批次

依赖（通过 __init__ 注入）：
- legacy_adapter: LegacyForeshadowingAdapter（只读）
- log_repository: MigrationLogRepository（migration_log 持久化）
- new_table_writer: NewForeshadowingWriter（new table INSERT 抽象）
- audit_service: MigrationAuditService（Group C 注入）
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from application.storyos.value_objects.migration_preview_report import (
    MigrationPreviewReport,
    MigrationSampleError,
)
from application.storyos.migration.status_mapper import StatusMapper, UnknownLegacyStatusError

logger = logging.getLogger(__name__)


@dataclass
class MigrationExecuteResult:
    migration_id: str
    status: str  # "completed" | "partial" | "failed"
    batches_total: int
    batches_done: int
    records_migrated: int
    errors: List[str] = field(default_factory=list)


@dataclass
class RollbackResult:
    migration_id: str
    records_deleted: int
    status: str  # "rolled_back" | "not_found" | "already_rolled_back"


class ForeshadowingMigrationService:
    """Foreshadowing 单向迁移服务（spec §1E）。"""

    def __init__(
        self,
        legacy_adapter,
        log_repository=None,
        new_table_writer=None,
        audit_service=None,
    ) -> None:
        self._legacy = legacy_adapter
        self._log_repo = log_repository
        self._new_writer = new_table_writer
        self._audit = audit_service

    def scan(self, project_id: str) -> MigrationPreviewReport:
        """扫描旧表生成预览报告（只读，不写任何表）。"""
        # count_for_novel 在 MagicMock 下默认返回 MagicMock（不可强制转 int）；
        # 因此在不可用时 fallback 到 scanned 作为 total。
        raw_total = self._legacy.count_for_novel(project_id)
        records, adapter_invalid_ids = self._legacy.fetch_all_with_invalid(project_id)
        scanned = len(records) + len(adapter_invalid_ids)
        total = raw_total if isinstance(raw_total, int) else scanned

        # 状态映射 + 跳过 invalid
        migratable_pairs, status_invalid_ids = StatusMapper.map_with_skip(records)
        migratable = len(migratable_pairs)
        invalid = len(adapter_invalid_ids) + len(status_invalid_ids)

        # 断点续跑：减去已迁移的（log_repo 可选 —— scan-only 测试可不传）
        if self._log_repo is not None:
            committed_ids = self._log_repo.get_committed_old_ids(project_id)
        else:
            committed_ids = set()
        skipped = sum(1 for r, _ in migratable_pairs if r.id in committed_ids)
        migratable -= skipped

        # sample errors（最多 10 条）
        sample_errors: List[MigrationSampleError] = []
        for bad_id in adapter_invalid_ids + status_invalid_ids:
            if len(sample_errors) >= 10:
                break
            code = "CORRUPTED_ROW" if bad_id in adapter_invalid_ids else "UNKNOWN_STATUS"
            sample_errors.append(MigrationSampleError(
                old_id=bad_id,
                code=code,
                message=f"Legacy foreshadowing {bad_id} cannot be migrated",
            ))

        return MigrationPreviewReport(
            project_id=project_id,
            total=total,
            scanned=scanned,
            migratable=migratable,
            skipped=skipped,
            invalid=invalid,
            sample_errors=sample_errors,
        )

    def execute(
        self,
        project_id: str,
        batch_size: int = 500,
        dry_run: bool = False,
    ) -> MigrationExecuteResult:
        """执行迁移。"""
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        # 1. 拉取旧表全量 + 过滤已 committed
        records, adapter_invalid_ids = self._legacy.fetch_all_with_invalid(project_id)
        committed_ids = self._log_repo.get_committed_old_ids(project_id)

        # 2. 状态映射 + 跳过 unknown status
        migratable_pairs, status_invalid_ids = StatusMapper.map_with_skip(records)
        migratable_pairs = [
            (r, s) for r, s in migratable_pairs if r.id not in committed_ids
        ]

        if dry_run:
            return MigrationExecuteResult(
                migration_id="dry-run",
                status="dry_run",
                batches_total=(len(migratable_pairs) + batch_size - 1) // batch_size,
                batches_done=0,
                records_migrated=0,
                errors=[],
            )

        # 3. 分批执行
        migration_id = f"mig-{uuid.uuid4().hex[:12]}"
        batches_total = (len(migratable_pairs) + batch_size - 1) // batch_size
        batches_done = 0
        successful_batch_sizes: List[int] = []
        errors: List[str] = []
        started_at = datetime.utcnow().isoformat()

        for batch_idx in range(batches_total):
            batch_start = batch_idx * batch_size
            batch_end = batch_start + batch_size
            batch = migratable_pairs[batch_start:batch_end]
            batch_id = f"batch-{batch_idx:04d}"
            old_ids = [r.id for r, _ in batch]

            try:
                self._new_writer.insert_batch(
                    [r for r, _ in batch],
                    [s for _, s in batch],
                )
                completed_at = datetime.utcnow().isoformat()
                self._log_repo.record_committed_batch(
                    migration_id=migration_id,
                    project_id=project_id,
                    batch_id=batch_id,
                    old_ids=old_ids,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                batches_done += 1
                successful_batch_sizes.append(len(batch))
            except Exception as e:
                error_msg = f"batch {batch_id} failed: {e}"
                logger.warning("[migration] %s", error_msg)
                errors.append(error_msg)
                self._log_repo.record_failed_batch(
                    migration_id=migration_id,
                    project_id=project_id,
                    batch_id=batch_id,
                    old_ids=old_ids,
                    started_at=started_at,
                    error=str(e),
                )

        # 4. 计算最终状态
        if batches_done == batches_total:
            status = "completed"
        elif batches_done == 0:
            status = "failed"
        else:
            status = "partial"

        records_migrated = sum(successful_batch_sizes)

        if self._audit is not None:
            try:
                self._audit.record_migration(
                    migration_id=migration_id,
                    project_id=project_id,
                    batches_total=batches_total,
                    batches_done=batches_done,
                    records_migrated=records_migrated,
                    errors=errors,
                )
            except Exception as e:
                logger.warning("[migration] audit record 失败: %s", e)

        return MigrationExecuteResult(
            migration_id=migration_id,
            status=status,
            batches_total=batches_total,
            batches_done=batches_done,
            records_migrated=records_migrated,
            errors=errors,
        )

    def rollback(self, migration_id: str) -> RollbackResult:
        """回滚单条迁移批次（只删新表，旧表不动，spec Q8）。"""
        entry = self._log_repo.get_entry(migration_id)
        if entry is None:
            return RollbackResult(
                migration_id=migration_id, records_deleted=0, status="not_found",
            )

        if entry.status.value == "rolled_back":
            return RollbackResult(
                migration_id=migration_id, records_deleted=0,
                status="already_rolled_back",
            )

        if entry.status.value != "committed":
            return RollbackResult(
                migration_id=migration_id, records_deleted=0,
                status="not_committed",
            )

        # 1. 删除新表数据（不走旧表）
        deleted = self._new_writer.delete_by_migrated_ids(entry.old_ids)

        # 2. 更新 migration_log 状态
        self._log_repo.mark_rolled_back(migration_id)

        return RollbackResult(
            migration_id=migration_id,
            records_deleted=deleted,
            status="rolled_back",
        )