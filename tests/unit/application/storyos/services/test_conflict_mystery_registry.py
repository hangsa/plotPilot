import pytest
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.mystery_registry_service import MysteryRegistryService
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.entities.mystery import Clue, Mystery


def test_conflict_registry_create_and_get():
    repo = {}
    svc = ConflictRegistryService(repository=repo)
    c = Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
        involved_characters=("a",), created_chapter=1,
    )
    svc.create(c)
    assert svc.get("c1") == c
    assert svc.list() == [c]


def test_conflict_registry_escalate():
    repo = {}
    svc = ConflictRegistryService(repository=repo)
    c = Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
        involved_characters=("a",), created_chapter=1,
    )
    svc.create(c)
    c2 = svc.update("c1", escalate=True)
    assert c2.intensity == ConflictIntensity.MEDIUM
    assert svc.get("c1").intensity == ConflictIntensity.MEDIUM  # 持久化


def test_mystery_registry_add_clue():
    repo = {}
    svc = MysteryRegistryService(repository=repo)
    m = Mystery(
        id="m1", novel_id="n1", description="x",
        status=AssetStatus.PLANTED, created_chapter=1,
    )
    svc.create(m)
    cl = Clue(id="cl1", mystery_id="m1", description="a",
              source_chapter=1, source_location="x")
    m2 = svc.add_clue("m1", cl)
    assert len(m2.clues) == 1
    # 持久化校验
    assert len(svc.get("m1").clues) == 1


def test_mystery_registry_add_clue_wrong_mystery_id_raises():
    repo = {}
    svc = MysteryRegistryService(repository=repo)
    m = Mystery(id="m1", novel_id="n1", description="x",
                status=AssetStatus.PLANTED, created_chapter=1)
    svc.create(m)
    cl = Clue(id="cl1", mystery_id="m2", description="a",  # 错配
              source_chapter=1, source_location="x")
    with pytest.raises(ValueError, match="!="):
        svc.add_clue("m1", cl)
