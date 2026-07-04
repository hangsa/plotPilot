from application.storyos.services.snapshot_projector import SnapshotProjector
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.mystery_registry_service import MysteryRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.entities.mystery import Mystery
from domain.storyos.entities.expectation import Expectation


def test_snapshot_projects_all_8_registries():
    conflict_svc = ConflictRegistryService()
    mystery_svc = MysteryRegistryService()
    expect_svc = ExpectationRegistryService()
    conflict_svc.create(Conflict(id="c1", novel_id="n1", description="x",
                                  intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
                                  involved_characters=("a",), created_chapter=1))
    mystery_svc.create(Mystery(id="m1", novel_id="n1", description="x",
                                status=AssetStatus.PLANTED, created_chapter=1))
    expect_svc.create(Expectation(id="e1", novel_id="n1", description="x",
                                   status=AssetStatus.ACTIVE, created_chapter=1, intensity=50))

    projector = SnapshotProjector(
        conflict_svc=conflict_svc, mystery_svc=mystery_svc, expectation_svc=expect_svc,
    )
    snap = projector.project(novel_id="n1")
    assert "conflict" in snap
    assert "mystery" in snap
    assert "expectation" in snap
    assert snap["conflict"]["c1"]["intensity"] == "LOW"
    assert snap["expectation"]["e1"]["intensity"] == 50
