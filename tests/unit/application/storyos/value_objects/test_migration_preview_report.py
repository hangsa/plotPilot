"""MigrationPreviewReport 5 元组 dataclass 测试。"""
from application.storyos.value_objects.migration_preview_report import (
    MigrationPreviewReport,
    MigrationSampleError,
)


def test_report_fields_default_to_zero():
    r = MigrationPreviewReport(project_id="n1")
    assert r.total == 0
    assert r.scanned == 0
    assert r.migratable == 0
    assert r.skipped == 0
    assert r.invalid == 0
    assert r.sample_errors == []


def test_report_full_construction():
    r = MigrationPreviewReport(
        project_id="n1",
        total=100,
        scanned=100,
        migratable=85,
        skipped=10,
        invalid=5,
        sample_errors=[
            MigrationSampleError(old_id="fs-3", code="UNKNOWN_STATUS", message="..."),
        ],
    )
    assert r.invalid == 5
    assert r.sample_errors[0].code == "UNKNOWN_STATUS"


def test_report_to_dict_snake_case_keys():
    """to_dict 输出 snake_case 键（与 1D DTO MigrationPreviewResponse 对齐）。"""
    r = MigrationPreviewReport(project_id="n1", total=10, scanned=10, migratable=8, skipped=1, invalid=1)
    d = r.to_dict()
    assert d["project_id"] == "n1"
    assert d["total"] == 10
    assert d["migratable"] == 8
    assert d["sample_errors"] == []