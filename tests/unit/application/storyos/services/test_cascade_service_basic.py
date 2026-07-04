import pytest
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.entities.expectation import Expectation


def test_cascade_conflift_escalated_increases_expectation():
    """CONFLICT_ESCALATED 触发 → linked expectation intensity +30（spec §4.2 锁定）。"""
    conflict_svc = ConflictRegistryService()
    expect_svc = ExpectationRegistryService()
    cascade = CascadeService(
        conflict_svc=conflict_svc, expectation_svc=expect_svc, max_depth=3,
    )
    c = Conflict(id="c1", novel_id="n1", description="x",
                 intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
                 involved_characters=("a",), created_chapter=1,
                 linked_conflicts=())
    conflict_svc.create(c)
    e = Expectation(id="e1", novel_id="n1", description="reader expects climax",
                    status=AssetStatus.ACTIVE, created_chapter=1, intensity=20)
    expect_svc.create(e)

    # 构造 cascade step：conflict c1 → expectation e1, +30 intensity
    step = CascadeStep(
        trigger=CascadeTrigger.CONFLICT_ESCALATED,
        source_asset_type="conflict", source_asset_id="c1",
        target_asset_type="expectation", target_asset_id="e1",
        intensity_delta=30, reason="conflict escalated",
    )
    result = cascade.execute([step])
    assert len(result.steps_executed) == 1
    assert expect_svc.get("e1").intensity == 50  # 20 + 30


def test_cascade_blocks_cycle():
    """级联深度超 max_depth → 阻断。"""
    expect_svc = ExpectationRegistryService()
    expect_svc.create(Expectation(id="e1", novel_id="n1", description="x",
                                  status=AssetStatus.ACTIVE,
                                  created_chapter=1, intensity=10))
    cascade = CascadeService(expectation_svc=expect_svc, max_depth=0)
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery", source_asset_id="m1",
        target_asset_type="expectation", target_asset_id="e1",
        new_status=AssetStatus.ACTIVE, reason="x",
    )
    result = cascade.execute([step])
    assert len(result.blocked_steps) == 1
    assert len(result.steps_executed) == 0