"""ForeshadowingMigrationService.scan() 单元测试。"""
from unittest.mock import MagicMock
from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingRecord,
)


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