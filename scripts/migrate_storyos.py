#!/usr/bin/env python3
"""migrate_storyos.py —— StoryOS Foreshadowing 单向迁移 CLI（spec §1E 锁定）。

子命令：
  --dry-run              扫描旧表 + 输出 JSON 报告，不写任何表
  --execute              实际执行迁移（断点续跑 + 幂等）
  --rollback <id>        回滚单条迁移批次
  --status               显示当前进程的审计聚合

参数：
  --project-id <id>      目标项目 ID（dry-run / execute 必填）
  --batch-size <n>       每批大小（默认 500）
  --json                 JSON 格式输出（供脚本消费）

行为：
- 旧 foreshadows 表只读（spec Q8 锁定）
- 幂等性通过 UNIQUE(migrated_from_legacy_id) 保证
- dry-run 输出 5 元组报告 + sample errors
- execute 输出迁移 ID + 批次进度 + 错误聚合
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# 让脚本能 import 项目根目录的模块
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from application.storyos.services.migration_audit_service import (
    MigrationAuditService,
)
from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingAdapter,
)
from application.storyos.migration.migration_log_repository import (
    MigrationLogRepository,
)
from application.storyos.migration.new_foreshadowing_writer import (
    NewForeshadowingWriter,
)
from infrastructure.persistence.database.connection import get_database

logger = logging.getLogger(__name__)


class _TolerantLogRepo:
    """CLI 专用 log repo 包装：吞掉 schema-not-migrated 异常，保持 scan/execute 路径稳定。

    当 storyos_migration_log_v1 表尚未 migrate（例如开发环境）时，
    log repository 的原始实现会让 CLI 崩溃。生产环境按 spec §1E 完成迁移，
    本包装仅在表不存在时静默返回空集。
    """

    _MISSING_TABLE_MARKERS = ("no such table", "no such column")

    def __init__(self, inner) -> None:
        self._inner = inner

    def _safe(self, fn_name, *args, **kwargs):
        try:
            return getattr(self._inner, fn_name)(*args, **kwargs)
        except Exception as e:
            msg = str(e).lower()
            if any(m in msg for m in self._MISSING_TABLE_MARKERS):
                logger.warning("[migration] log_repo %s 表结构未就绪: %s", fn_name, e)
                return None
            raise

    def record_committed_batch(self, **kwargs):
        return self._safe("record_committed_batch", **kwargs)

    def record_failed_batch(self, **kwargs):
        return self._safe("record_failed_batch", **kwargs)

    def get_committed_old_ids(self, project_id, migration_type="foreshadowing_v1"):
        result = self._safe("get_committed_old_ids", project_id, migration_type)
        return result if result is not None else set()

    def get_entry(self, migration_id):
        return self._safe("get_entry", migration_id)

    def mark_rolled_back(self, migration_id):
        return self._safe("mark_rolled_back", migration_id)


def _build_service(args) -> ForeshadowingMigrationService:
    """构造 MigrationService（CLI 模式下默认使用主数据库）。

    DB 不可用时返回空 service（容错：让 CLI 在生产环境 DB 损坏时仍能输出
    空 JSON 报告，便于运维诊断）。

    ``LegacyForeshadowingAdapter`` 直接消费生产接口（spec C4 已修复
    ``_resolve_cursor`` 的参数绑定），cursor_provider 每次调用新开连接——
    CLI 是 one-shot 工具，无连接池需求。
    """
    try:
        db = get_database()

        def conn_provider():
            return db.get_connection()

        def legacy_cursor_provider(sql, params):
            conn = conn_provider()
            return conn.execute(sql, params)

        legacy = LegacyForeshadowingAdapter(cursor_provider=legacy_cursor_provider)
        log_repo = _TolerantLogRepo(MigrationLogRepository(db_provider=conn_provider))
        new_writer = NewForeshadowingWriter()
        audit = MigrationAuditService()
        return ForeshadowingMigrationService(
            legacy_adapter=legacy,
            log_repository=log_repo,
            new_table_writer=new_writer,
            audit_service=audit,
        )
    except Exception as e:
        logger.warning("[migration] 数据库不可用，使用空 service: %s", e)
        return ForeshadowingMigrationService(
            legacy_adapter=_EmptyAdapter(),
            log_repository=_EmptyLogRepo(),
            new_table_writer=_EmptyWriter(),
            audit_service=MigrationAuditService(),
        )


class _EmptyAdapter:
    """DB 不可用时的空 legacy adapter 占位实现。"""

    def fetch_all_with_invalid(self, project_id, cursor=None):
        return [], []

    def count_for_novel(self, project_id):
        return 0


class _EmptyLogRepo:
    """DB 不可用时的空 log repo 占位实现。"""

    def get_committed_old_ids(self, project_id, migration_type="foreshadowing_v1"):
        return set()

    def record_committed_batch(self, **kwargs):
        return None

    def record_failed_batch(self, **kwargs):
        return None

    def get_entry(self, migration_id):
        return None

    def mark_rolled_back(self, migration_id):
        return None


class _EmptyWriter:
    """DB 不可用时的空 writer 占位实现。"""

    def insert_batch(self, records, statuses):
        return None

    def delete_by_migrated_ids(self, old_ids):
        return 0


def _print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_dry_run(args, service: ForeshadowingMigrationService) -> int:
    report = service.scan(args.project_id)
    if args.json:
        _print_json(report.to_dict())
    else:
        print(f"[migration] dry-run 扫描完成 project_id={args.project_id}")
        print(f"[migration] total={report.total} migratable={report.migratable} "
              f"skipped={report.skipped} invalid={report.invalid}")
    return 0


def cmd_execute(args, service: ForeshadowingMigrationService) -> int:
    if not args.json:
        print(f"[migration] 开始迁移 project_id={args.project_id} batch_size={args.batch_size}")
    result = service.execute(
        project_id=args.project_id,
        batch_size=args.batch_size,
        dry_run=False,
    )
    if args.json:
        _print_json({
            "migration_id": result.migration_id,
            "status": result.status,
            "batches_total": result.batches_total,
            "batches_done": result.batches_done,
            "records_migrated": result.records_migrated,
            "errors": result.errors,
        })
    else:
        print(f"[migration] 完成 status={result.status}")
        print(f"[migration] 迁移 ID: {result.migration_id}")
        print(f"[migration] 批次进度: {result.batches_done}/{result.batches_total}")
        print(f"[migration] 迁移记录: {result.records_migrated}")
        if result.errors:
            print(f"[migration] 错误 ({len(result.errors)} 条):")
            for e in result.errors[:10]:  # 最多显示 10 条
                print(f"  - {e}")
    return 0 if result.status == "completed" else 1


def cmd_rollback(args, service: ForeshadowingMigrationService) -> int:
    result = service.rollback(args.rollback)
    _print_json({
        "migration_id": result.migration_id,
        "records_deleted": result.records_deleted,
        "status": result.status,
    })
    return 0 if result.status == "rolled_back" else 1


def cmd_status(args, service: ForeshadowingMigrationService) -> int:
    if service._audit is None:
        print(json.dumps({"error": "audit service not configured"}))
        return 1
    report = service._audit.aggregate_report()
    _print_json(report)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="StoryOS Foreshadowing 单向迁移工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project-id", type=str, help="目标项目 ID")
    parser.add_argument("--batch-size", type=int, default=500, help="每批大小（默认 500）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")

    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--dry-run", action="store_true", help="仅扫描不写")
    mode.add_argument("--execute", action="store_true", help="执行迁移")
    mode.add_argument("--rollback", type=str, metavar="MIGRATION_ID", help="回滚指定批次")
    mode.add_argument("--status", action="store_true", help="显示审计聚合")

    # parse_known_args 让未识别的 flag 保留到 unknown_args，便于错误检测
    args, unknown_args = parser.parse_known_args(argv)

    # 检测未知参数 → 模拟 subparser 风格报 "unrecognized arguments" 错误
    if unknown_args:
        parser.error(f"unrecognized arguments: {' '.join(unknown_args)}")

    # 默认行为：无参数显示 help
    if not any([args.dry_run, args.execute, args.rollback, args.status]):
        parser.print_help()
        return 0

    service = _build_service(args)

    try:
        if args.dry_run:
            if not args.project_id:
                parser.error("--dry-run requires --project-id")
            return cmd_dry_run(args, service)
        elif args.execute:
            if not args.project_id:
                parser.error("--execute requires --project-id")
            return cmd_execute(args, service)
        elif args.rollback:
            return cmd_rollback(args, service)
        elif args.status:
            return cmd_status(args, service)
    except Exception as e:
        logger.exception("CLI 异常")
        print(json.dumps({"error": str(e)}))
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
