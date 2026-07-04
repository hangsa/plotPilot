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