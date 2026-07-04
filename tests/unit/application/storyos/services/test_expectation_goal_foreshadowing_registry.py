from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from application.storyos.services.goal_registry_service import GoalRegistryService
from application.storyos.services.foreshadowing_registry_service import ForeshadowingRegistryService
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.expectation import Expectation
from domain.storyos.entities.goal import Goal, ProgressMarker
from domain.storyos.entities.foreshadowing import Foreshadowing
from domain.novel.value_objects.foreshadowing import ImportanceLevel


def test_expectation_intensify_clamps_in_service():
    svc = ExpectationRegistryService()
    e = Expectation(id="e1", novel_id="n1", description="x",
                    status=AssetStatus.ACTIVE, created_chapter=1, intensity=95)
    svc.create(e)
    e2 = svc.intensify("e1", delta=30)
    assert e2.intensity == 100


def test_goal_advance_via_service():
    svc = GoalRegistryService()
    g = Goal(id="g1", novel_id="n1", description="x",
             status=AssetStatus.ACTIVE, created_chapter=1,
             current_progress=ProgressMarker.T3)
    svc.create(g)
    g2 = svc.advance("g1", ProgressMarker.T5)
    assert g2.current_progress == ProgressMarker.T5


def test_foreshadowing_resolve_via_service():
    svc = ForeshadowingRegistryService()
    f = Foreshadowing(id="fs1", novel_id="n1", description="x",
                     importance=ImportanceLevel.HIGH,
                     status=AssetStatus.PLANTED, planted_in_chapter=2)
    svc.create(f)
    f2 = svc.resolve("fs1", chapter=10)
    assert f2.status == AssetStatus.REVEALED
    assert f2.resolved_in_chapter == 10