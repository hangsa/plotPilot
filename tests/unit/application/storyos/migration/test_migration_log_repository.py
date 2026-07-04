"""migration_log_repository 单元测试。

migration_log 表（spec §1E 锁定）持久化每个批次的状态，支持：
- 断点续跑：查询已 committed 的 old_ids 集合
- 回滚：通过 migration_id 删除对应批次 + 更新 log.status
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from application.storyos.migration.migration_log_repository import (
    MigrationLogRepository,
    MigrationLogEntry,
    MigrationStatus,
)


@pytest.fixture
def fake_db():
    db = MagicMock()
    # fetchall 返回已迁移的 old_id 列表
    db.execute.return_value.fetchall.return_value = [
        ("fs-1",), ("fs-2",), ("fs-3",),
    ]
    db.execute.return_value.fetchone.return_value = None
    return db


def test_migration_status_enum_members():
    """MigrationStatus 3 值：committed / failed / rolled_back（spec §1E 锁定）。"""
    assert MigrationStatus.COMMITTED.value == "committed"
    assert MigrationStatus.FAILED.value == "failed"
    assert MigrationStatus.ROLLED_BACK.value == "rolled_back"


def test_migration_log_entry_fields():
    """MigrationLogEntry 9 字段（含 spec §1E 锁定的 schema）。"""
    entry = MigrationLogEntry(
        id="ml-1",
        project_id="novel-1",
        migration_type="foreshadowing_v1",
        batch_id="batch-001",
        old_ids=["fs-1", "fs-2"],
        status=MigrationStatus.COMMITTED,
        started_at="2026-07-03T10:00:00",
        completed_at="2026-07-03T10:00:05",
        error=None,
    )
    assert entry.migration_type == "foreshadowing_v1"
    assert entry.status == MigrationStatus.COMMITTED
    assert len(entry.old_ids) == 2


def test_repo_records_committed_batch(fake_db):
    """record_committed_batch 写入一条 committed 记录。"""
    repo = MigrationLogRepository(db_provider=lambda: fake_db)
    repo.record_committed_batch(
        migration_id="ml-1",
        project_id="novel-1",
        batch_id="batch-001",
        old_ids=["fs-1", "fs-2"],
        started_at="2026-07-03T10:00:00",
        completed_at="2026-07-03T10:00:05",
    )
    fake_db.execute.assert_called()
    sql = fake_db.execute.call_args.args[0]
    assert "INSERT" in sql.upper()
    assert "migration_log" in sql or "storyos_migration_log" in sql


def test_repo_records_failed_batch(fake_db):
    """record_failed_batch 写入一条 failed 记录（含 error 信息）。"""
    repo = MigrationLogRepository(db_provider=lambda: fake_db)
    repo.record_failed_batch(
        migration_id="ml-2",
        project_id="novel-1",
        batch_id="batch-002",
        old_ids=["fs-3"],
        started_at="2026-07-03T10:00:00",
        error="UNIQUE constraint failed",
    )
    sql = fake_db.execute.call_args.args[0]
    assert "INSERT" in sql.upper()
    params = fake_db.execute.call_args.args[1]
    assert "failed" in params or "UNIQUE constraint" in str(params)


def test_repo_get_committed_old_ids_returns_set(fake_db):
    """get_committed_old_ids 返回已迁移 old_id 集合（供断点续跑）。"""
    repo = MigrationLogRepository(db_provider=lambda: fake_db)
    committed = repo.get_committed_old_ids("novel-1", migration_type="foreshadowing_v1")
    assert committed == {"fs-1", "fs-2", "fs-3"}
    sql = fake_db.execute.call_args.args[0]
    params = fake_db.execute.call_args.args[1]
    assert "committed" in sql
    # migration_type 通过参数化传入（避免 SQL 注入）
    assert "foreshadowing_v1" in params


def test_repo_mark_rolled_back_updates_status(fake_db):
    """mark_rolled_back 把 committed → rolled_back（rollback 流程）。"""
    repo = MigrationLogRepository(db_provider=lambda: fake_db)
    repo.mark_rolled_back("ml-1")
    sql = fake_db.execute.call_args.args[0]
    assert "UPDATE" in sql.upper()
    assert "rolled_back" in sql


def test_repo_get_entry_by_id(fake_db):
    """get_entry 返回单条 MigrationLogEntry。"""
    fake_db.execute.return_value.fetchone.return_value = (
        "ml-1", "novel-1", "foreshadowing_v1", "batch-001",
        '["fs-1","fs-2"]', "committed",
        "2026-07-03T10:00:00", "2026-07-03T10:00:05", None,
    )
    repo = MigrationLogRepository(db_provider=lambda: fake_db)
    entry = repo.get_entry("ml-1")
    assert entry is not None
    assert entry.id == "ml-1"
    assert entry.old_ids == ["fs-1", "fs-2"]