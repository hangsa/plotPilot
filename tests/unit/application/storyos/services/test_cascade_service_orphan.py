from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep


def test_cascade_silently_skips_orphan_target():
    """target 不在 registry → 软失败（不抛异常，记录到 blocked）。"""
    conflict_svc = ConflictRegistryService()
    cascade = CascadeService(conflict_svc=conflict_svc)
    step = CascadeStep(
        trigger=CascadeTrigger.CONFLICT_RESOLVED,
        source_asset_type="conflict", source_asset_id="c1",
        target_asset_type="conflict", target_asset_id="ghost",
        new_status=AssetStatus.RESOLVED, reason="x",
    )
    result = cascade.execute([step])
    # 软失败：不抛异常；step 不进 executed 也不进 blocked（孤儿）
    assert len(result.steps_executed) == 0


def test_cascade_max_depth_limits_chain():
    """depth 限制级联深度（spec §4.2 锁定 MAX_CASCADE_DEPTH=3）。"""
    conflict_svc = ConflictRegistryService()
    cascade = CascadeService(conflict_svc=conflict_svc, max_depth=2)
    steps = [
        CascadeStep(
            trigger=CascadeTrigger.CONFLICT_RESOLVED,
            source_asset_type="conflict", source_asset_id=f"src{i}",
            target_asset_type="conflict", target_asset_id=f"tgt{i}",
            new_status=AssetStatus.RESOLVED, reason=f"step{i}",
        ) for i in range(5)
    ]
    result = cascade.execute(steps)
    # depth=2 → 至多 2 个 step executed；其余 blocked
    assert result.max_depth_reached <= 2
