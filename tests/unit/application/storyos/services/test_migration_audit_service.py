"""MigrationAuditService 单元测试。

audit 聚合每个 migration_id 的批次结果，生成最终 JSON 报告。
存储在内存（不需要持久化表）；CLI / API 退出时打印。
"""
from application.storyos.services.migration_audit_service import (
    MigrationAuditService,
    MigrationAuditRecord,
)


def test_audit_service_starts_empty():
    svc = MigrationAuditService()
    assert svc.all_records() == []


def test_record_migration_creates_record():
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1",
        project_id="novel-1",
        batches_total=4,
        batches_done=4,
        records_migrated=100,
        errors=[],
    )
    records = svc.all_records()
    assert len(records) == 1
    assert records[0].migration_id == "mig-1"
    assert records[0].records_migrated == 100


def test_record_migration_captures_errors():
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1",
        project_id="novel-1",
        batches_total=4,
        batches_done=2,
        records_migrated=50,
        errors=["batch-0002 failed: SQL", "batch-0003 failed: timeout"],
    )
    rec = svc.all_records()[0]
    assert len(rec.errors) == 2
    assert "SQL" in rec.errors[0]


def test_get_record_returns_by_migration_id():
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1", project_id="n1",
        batches_total=1, batches_done=1, records_migrated=10, errors=[],
    )
    svc.record_migration(
        migration_id="mig-2", project_id="n1",
        batches_total=2, batches_done=2, records_migrated=20, errors=[],
    )
    rec = svc.get_record("mig-1")
    assert rec is not None
    assert rec.records_migrated == 10
    assert svc.get_record("mig-999") is None


def test_audit_record_fields():
    """MigrationAuditRecord 字段集：8 字段覆盖批次 + 项目 + 错误。"""
    rec = MigrationAuditRecord(
        migration_id="mig-1", project_id="n1",
        batches_total=5, batches_done=5, records_migrated=100,
        duration_ms=1500, status="completed", errors=[],
        started_at="2026-07-03T10:00:00",
    )
    assert rec.duration_ms == 1500
    assert rec.status == "completed"


def test_aggregator_combines_multiple_migrations():
    """aggregator 合并多个 migration_id 的审计记录，生成最终报告。"""
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1", project_id="n1",
        batches_total=2, batches_done=2, records_migrated=100, errors=[],
    )
    svc.record_migration(
        migration_id="mig-2", project_id="n1",
        batches_total=3, batches_done=2, records_migrated=80,
        errors=["batch-0003 failed"],
    )
    report = svc.aggregate_report()
    assert report["total_migrations"] == 2
    assert report["total_records_migrated"] == 180
    assert report["total_errors"] == 1


def test_aggregator_returns_empty_report_when_no_records():
    svc = MigrationAuditService()
    report = svc.aggregate_report()
    assert report["total_migrations"] == 0
    assert report["total_records_migrated"] == 0
    assert report["migrations"] == []


def test_aggregator_groups_by_project_id():
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1", project_id="n1",
        batches_total=1, batches_done=1, records_migrated=10, errors=[],
    )
    svc.record_migration(
        migration_id="mig-2", project_id="n2",
        batches_total=1, batches_done=1, records_migrated=20, errors=[],
    )
    report = svc.aggregate_report()
    by_project = report["by_project"]
    assert by_project["n1"] == {"migrations": 1, "records": 10}
    assert by_project["n2"] == {"migrations": 1, "records": 20}


def test_aggregator_to_json_serializable():
    """aggregator 输出的 dict 可以直接 json.dumps。"""
    import json
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1", project_id="n1",
        batches_total=1, batches_done=1, records_migrated=10, errors=[],
    )
    report = svc.aggregate_report()
    json_str = json.dumps(report)
    assert "mig-1" in json_str