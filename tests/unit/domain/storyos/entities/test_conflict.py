import pytest

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity


def test_conflict_intensity_has_4_levels():
    assert {m.name for m in ConflictIntensity} == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert ConflictIntensity.LOW.value == 1
    assert ConflictIntensity.CRITICAL.value == 4


def test_conflict_minimum_required():
    c = Conflict(
        id="c1",
        novel_id="n1",
        description="alice vs bob",
        intensity=ConflictIntensity.MEDIUM,
        status=AssetStatus.ACTIVE,
        involved_characters=("alice", "bob"),
        created_chapter=1,
    )
    assert c.id == "c1"
    assert c.intensity == ConflictIntensity.MEDIUM
    assert c.linked_conflicts == ()


def test_conflict_escalate_low_to_medium():
    c = Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
        involved_characters=("a",), created_chapter=1,
    )
    c2 = c.escalate()
    assert c2.intensity == ConflictIntensity.MEDIUM
    assert c2.id == c.id
    assert c2 is not c  # new object


def test_conflict_escalate_critical_raises():
    c = Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.CRITICAL, status=AssetStatus.ACTIVE,
        involved_characters=("a",), created_chapter=1,
    )
    with pytest.raises(ValueError, match="already CRITICAL"):
        c.escalate()


def test_conflict_forbids_extra():
    with pytest.raises(TypeError):
        Conflict(
            id="c1", novel_id="n1", description="x",
            intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
            involved_characters=("a",), created_chapter=1,
            extra_field="nope",  # type: ignore[call-arg]
        )
