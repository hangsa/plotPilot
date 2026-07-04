"""C4 — CascadeService.simulate dry-run preview (spec §4.1 Step 3)."""
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.entities.expectation import Expectation


def test_cascade_simulate_returns_preview_without_applying():
    """spec §4.1 Step 3 dry-run：模拟级联但不实际应用（1D 前端消费）。"""
    conflict_svc = ConflictRegistryService()
    expect_svc = ExpectationRegistryService()
    conflict_svc.create(Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.MEDIUM, status=AssetStatus.ACTIVE,
        involved_characters=("a",), created_chapter=1,
    ))
    expect_svc.create(Expectation(
        id="e1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1, intensity=20,
    ))
    cascade = CascadeService(conflict_svc=conflict_svc, expectation_svc=expect_svc)
    preview = cascade.simulate(
        trigger=CascadeTrigger.CONFLICT_ESCALATED,
        source_asset_type="conflict", source_asset_id="c1",
        target_asset_type="expectation", target_asset_id="e1",
        intensity_delta=30,
    )
    # simulate 不修改状态
    assert expect_svc.get("e1").intensity == 20
    # preview 含预期结果
    assert preview.predicted_intensity == 50
    assert preview.would_block is False
