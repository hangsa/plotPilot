import pytest
from application.storyos.services.foreshadowing_migration_service import ForeshadowingMigrationService


def test_migration_service_scan_is_not_implemented():
    """1B 留 stub；1E 阶段实现 scan/execute/rollback。"""
    svc = ForeshadowingMigrationService()
    with pytest.raises(NotImplementedError, match="Phase 1E"):
        svc.scan()


def test_migration_service_execute_is_not_implemented():
    svc = ForeshadowingMigrationService()
    with pytest.raises(NotImplementedError, match="Phase 1E"):
        svc.execute(batch_size=500)


def test_migration_service_rollback_is_not_implemented():
    svc = ForeshadowingMigrationService()
    with pytest.raises(NotImplementedError, match="Phase 1E"):
        svc.rollback(migration_id="m1")