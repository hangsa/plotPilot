"""ForeshadowingMigrationService.scan() 单元测试。"""
from unittest.mock import MagicMock
from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingRecord,
)


def _make_service(records, committed_ids=None, adapter_invalid=None):
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = (
        records,
        adapter_invalid or [],
    )
    log_repo = MagicMock()
    log_repo.get_committed_old_ids.return_value = committed_ids or set()
    new_writer = MagicMock()
    return ForeshadowingMigrationService(
        legacy_adapter=adapter,
        log_repository=log_repo,
        new_table_writer=new_writer,
    ), adapter, log_repo, new_writer


def _fake_records():
    return [
        LegacyForeshadowingRecord(
            id=f"fs-{i}", novel_id="n1", description=f"d{i}",
            planted_chapter=i, due_chapter=None, resolved_chapter=None,
            status="planted" if i % 3 == 0 else ("resolved" if i % 3 == 1 else "abandoned"),
            importance=2, subtext_type=None,
        )
        for i in range(1, 11)
    ]


def test_scan_returns_5_tuple_report():
    """scan 返回 5 元组：total/scanned/migratable/skipped/invalid。"""
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = (_fake_records(), [])
    service = ForeshadowingMigrationService(legacy_adapter=adapter)
    report = service.scan("novel-1")
    assert report.total == 10
    assert report.scanned == 10
    assert report.migratable == 10  # 所有 10 条都映射成功
    assert report.invalid == 0


def test_scan_partitions_invalid_ids():
    """scan 把损坏 / 未知 status 的记录计入 invalid。"""
    records = _fake_records()
    records.append(LegacyForeshadowingRecord(
        id="fs-bad", novel_id="n1", description="d",
        planted_chapter=1, due_chapter=None, resolved_chapter=None,
        status="legacy_weird", importance=2, subtext_type=None,
    ))
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = (records, [])
    service = ForeshadowingMigrationService(legacy_adapter=adapter)
    report = service.scan("novel-1")
    assert report.migratable == 10
    assert report.invalid == 1
    assert any(e.old_id == "fs-bad" for e in report.sample_errors)


def test_scan_partitions_adapter_corrupted_rows():
    """scan 也接收 adapter 返回的 invalid_ids（field 损坏行）。"""
    records = _fake_records()
    records.append(LegacyForeshadowingRecord(
        id="fs-bad", novel_id="n1", description="d",
        planted_chapter=1, due_chapter=None, resolved_chapter=None,
        status="legacy_weird", importance=2, subtext_type=None,
    ))
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = (records, ["fs-corrupt-1", "fs-corrupt-2"])
    service = ForeshadowingMigrationService(legacy_adapter=adapter)
    report = service.scan("novel-1")
    assert report.invalid == 3  # 1 unknown status + 2 corrupted
    assert report.migratable == 10


def test_scan_empty_project_returns_zero_report():
    """空项目 scan 返回全 0 报告，不抛异常。"""
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = ([], [])
    service = ForeshadowingMigrationService(legacy_adapter=adapter)
    report = service.scan("novel-empty")
    assert report.total == 0
    assert report.scanned == 0
    assert report.migratable == 0


def test_scan_does_not_modify_database():
    """scan 是只读操作（不能写 migration_log 或新表）。"""
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = (_fake_records(), [])
    log_repo = MagicMock()
    service = ForeshadowingMigrationService(
        legacy_adapter=adapter, log_repository=log_repo,
    )
    service.scan("novel-1")
    # log_repository 不能被 scan 调用任何写方法
    log_repo.record_committed_batch.assert_not_called()
    log_repo.record_failed_batch.assert_not_called()


"""ForeshadowingMigrationService.execute() 单元测试。"""


def test_execute_happy_path_single_batch():
    """execute 单一批次 < 500：直接迁移 + record committed。"""
    records = _fake_records()  # 10 条
    service, _, log_repo, new_writer = _make_service(records)
    result = service.execute("novel-1", batch_size=500)
    assert result.batches_total == 1
    assert result.batches_done == 1
    assert result.records_migrated == 10
    assert result.status == "completed"
    new_writer.insert_batch.assert_called_once()
    log_repo.record_committed_batch.assert_called_once()


def test_execute_multiple_batches():
    """execute batch_size=3 → 10 条 → 4 batches（3+3+3+1）。"""
    records = _fake_records()
    service, _, _, new_writer = _make_service(records)
    result = service.execute("novel-1", batch_size=3)
    assert result.batches_total == 4
    assert result.batches_done == 4
    assert result.records_migrated == 10
    assert new_writer.insert_batch.call_count == 4


def test_execute_skips_already_committed_ids():
    """断点续跑：已 committed 的 old_ids 跳过（不入 batch）。"""
    records = _fake_records()  # 10 条
    committed = {"fs-1", "fs-2", "fs-3"}
    service, _, log_repo, new_writer = _make_service(records, committed_ids=committed)
    result = service.execute("novel-1", batch_size=500)
    assert result.records_migrated == 7  # 10 - 3 already migrated
    new_writer.insert_batch.assert_called_once()
    inserted_batch = new_writer.insert_batch.call_args.args[0]
    inserted_ids = [r.id for r in inserted_batch]
    assert "fs-1" not in inserted_ids


def test_execute_dry_run_does_not_write():
    """dry_run=True：不调用 new_writer.insert_batch + 不写 migration_log。"""
    records = _fake_records()
    service, _, log_repo, new_writer = _make_service(records)
    result = service.execute("novel-1", batch_size=500, dry_run=True)
    assert result.status == "dry_run"
    new_writer.insert_batch.assert_not_called()
    log_repo.record_committed_batch.assert_not_called()


def test_execute_handles_invalid_status_gracefully():
    """未知 status 的记录跳过（不入 batch）但不抛异常。"""
    records = _fake_records()
    records.append(LegacyForeshadowingRecord(
        id="fs-bad", novel_id="n1", description="d",
        planted_chapter=1, due_chapter=None, resolved_chapter=None,
        status="legacy_weird", importance=2, subtext_type=None,
    ))
    service, _, _, new_writer = _make_service(records)
    result = service.execute("novel-1", batch_size=500)
    assert result.records_migrated == 10
    inserted_batch = new_writer.insert_batch.call_args.args[0]
    assert all(r.id != "fs-bad" for r in inserted_batch)


def test_execute_records_failed_batch_on_writer_exception():
    """writer 抛异常时调用 log_repo.record_failed_batch（不中断整个 migration）。"""
    records = _fake_records()
    service, _, log_repo, new_writer = _make_service(records)
    new_writer.insert_batch.side_effect = RuntimeError("SQL constraint failed")
    result = service.execute("novel-1", batch_size=3)
    # 4 个批次全部失败，但 service 不抛异常
    assert result.status == "failed"
    assert "SQL constraint" in str(result.errors)
    assert log_repo.record_failed_batch.call_count == 4


def test_execute_returns_partial_status_on_some_failed_batches():
    """部分批次失败时返回 partial 状态。"""
    records = _fake_records()
    service, _, _, new_writer = _make_service(records)
    # 第 2 个 batch 失败
    new_writer.insert_batch.side_effect = [
        None,  # batch 1 OK
        RuntimeError("batch 2 fail"),
        None,  # batch 3 OK
        None,  # batch 4 OK
    ]
    result = service.execute("novel-1", batch_size=3)
    assert result.status == "partial"
    assert result.batches_done == 3  # 4 中 3 成功


"""ForeshadowingMigrationService.rollback() 单元测试。"""


def test_rollback_deletes_new_records_and_marks_log():
    """rollback 删除新表数据 + 把 migration_log 标记为 rolled_back。"""
    from infrastructure.persistence.storyos.migration_log_mapper import (
        MigrationLogEntry, MigrationStatus,
    )
    entry = MigrationLogEntry(
        id="ml-1", project_id="n1", migration_type="foreshadowing_v1",
        batch_id="batch-0001", old_ids=["fs-1", "fs-2", "fs-3"],
        status=MigrationStatus.COMMITTED,
        started_at="2026-07-03T10:00:00", completed_at="2026-07-03T10:00:05",
        error=None,
    )
    log_repo = MagicMock()
    log_repo.get_entry.return_value = entry
    new_writer = MagicMock()
    new_writer.delete_by_migrated_ids.return_value = 3

    service = ForeshadowingMigrationService(
        legacy_adapter=MagicMock(),
        log_repository=log_repo,
        new_table_writer=new_writer,
    )
    result = service.rollback("ml-1")

    assert result.records_deleted == 3
    assert result.status == "rolled_back"
    new_writer.delete_by_migrated_ids.assert_called_once_with(["fs-1", "fs-2", "fs-3"])
    log_repo.mark_rolled_back.assert_called_once_with("ml-1")


def test_rollback_returns_not_found_when_log_missing():
    """migration_id 不存在时返回 not_found，不抛异常。"""
    log_repo = MagicMock()
    log_repo.get_entry.return_value = None
    new_writer = MagicMock()

    service = ForeshadowingMigrationService(
        legacy_adapter=MagicMock(),
        log_repository=log_repo,
        new_table_writer=new_writer,
    )
    result = service.rollback("ml-nonexistent")
    assert result.status == "not_found"
    assert result.records_deleted == 0
    new_writer.delete_by_migrated_ids.assert_not_called()


def test_rollback_returns_already_when_already_rolled_back():
    """已 rolled_back 的批次不能再次 rollback。"""
    from infrastructure.persistence.storyos.migration_log_mapper import (
        MigrationLogEntry, MigrationStatus,
    )
    entry = MigrationLogEntry(
        id="ml-1", project_id="n1", migration_type="foreshadowing_v1",
        batch_id="batch-0001", old_ids=["fs-1"],
        status=MigrationStatus.ROLLED_BACK,
        started_at="2026-07-03T10:00:00", completed_at=None, error=None,
    )
    log_repo = MagicMock()
    log_repo.get_entry.return_value = entry

    service = ForeshadowingMigrationService(
        legacy_adapter=MagicMock(),
        log_repository=log_repo,
        new_table_writer=MagicMock(),
    )
    result = service.rollback("ml-1")
    assert result.status == "already_rolled_back"


def test_rollback_returns_failed_status_when_already_failed():
    """失败批次不能 rollback（没有 committed 数据可回滚）。"""
    from infrastructure.persistence.storyos.migration_log_mapper import (
        MigrationLogEntry, MigrationStatus,
    )
    entry = MigrationLogEntry(
        id="ml-1", project_id="n1", migration_type="foreshadowing_v1",
        batch_id="batch-0001", old_ids=["fs-1"],
        status=MigrationStatus.FAILED,
        started_at="2026-07-03T10:00:00", completed_at=None, error="...",
    )
    log_repo = MagicMock()
    log_repo.get_entry.return_value = entry

    service = ForeshadowingMigrationService(
        legacy_adapter=MagicMock(),
        log_repository=log_repo,
        new_table_writer=MagicMock(),
    )
    result = service.rollback("ml-1")
    assert result.status == "not_committed"


def test_rollback_does_not_modify_legacy_table():
    """rollback 永远不删除旧表数据（spec Q8 锁定）。"""
    from infrastructure.persistence.storyos.migration_log_mapper import (
        MigrationLogEntry, MigrationStatus,
    )
    entry = MigrationLogEntry(
        id="ml-1", project_id="n1", migration_type="foreshadowing_v1",
        batch_id="batch-0001", old_ids=["fs-1"],
        status=MigrationStatus.COMMITTED,
        started_at="2026-07-03T10:00:00", completed_at="2026-07-03T10:00:05",
        error=None,
    )
    legacy = MagicMock()
    log_repo = MagicMock()
    log_repo.get_entry.return_value = entry
    new_writer = MagicMock()

    service = ForeshadowingMigrationService(
        legacy_adapter=legacy, log_repository=log_repo, new_table_writer=new_writer,
    )
    service.rollback("ml-1")
    # 严禁访问 legacy adapter
    legacy.fetch_all_with_invalid.assert_not_called()
    legacy.count_for_novel.assert_not_called()