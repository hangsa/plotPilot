import pytest

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.mystery import Clue, ClueCategory, Mystery


def test_clue_category_has_5_values():
    assert {m.name for m in ClueCategory} == {
        "TRUTH", "RELATIONSHIP", "IDENTITY", "ABILITY", "OTHER",
    }


def test_clue_minimum_required():
    c = Clue(
        id="cl1",
        mystery_id="m1",
        description="blood on the knife",
        source_chapter=2,
        source_location="kitchen",
    )
    assert c.status == AssetStatus.PLANTED
    assert c.category == ClueCategory.TRUTH
    assert c.discovered_in_chapter is None
    assert c.invalidated_in_chapter is None


def test_clue_discover_returns_new():
    c = Clue(
        id="cl1", mystery_id="m1", description="x",
        source_chapter=2, source_location="loc",
    )
    c2 = c.discover(chapter=5)
    assert c2 is not c
    assert c2.status == AssetStatus.REVEALED
    assert c2.discovered_in_chapter == 5


def test_clue_discover_must_be_after_source():
    c = Clue(
        id="cl1", mystery_id="m1", description="x",
        source_chapter=5, source_location="loc",
    )
    with pytest.raises(ValueError, match="< source_chapter"):
        c.discover(chapter=2)


def test_clue_invalidate_from_planted():
    c = Clue(
        id="cl1", mystery_id="m1", description="x",
        source_chapter=2, source_location="loc",
    )
    c2 = c.invalidate(chapter=8)
    assert c2.status == AssetStatus.DEAD
    assert c2.invalidated_in_chapter == 8


def test_clue_invalidate_from_revealed():
    c = Clue(
        id="cl1", mystery_id="m1", description="x",
        source_chapter=2, source_location="loc",
        status=AssetStatus.REVEALED, discovered_in_chapter=5,
    )
    c2 = c.invalidate(chapter=8)
    assert c2.status == AssetStatus.DEAD


def test_clue_invalidate_from_dead_raises():
    c = Clue(
        id="cl1", mystery_id="m1", description="x",
        source_chapter=2, source_location="loc",
        status=AssetStatus.DEAD, invalidated_in_chapter=8,
    )
    with pytest.raises(ValueError, match="Cannot invalidate clue in status"):
        c.invalidate(chapter=9)


def test_mystery_with_clues():
    cl1 = Clue(id="cl1", mystery_id="m1", description="a", source_chapter=1, source_location="x")
    cl2 = Clue(id="cl2", mystery_id="m1", description="b", source_chapter=2, source_location="y")
    m = Mystery(
        id="m1", novel_id="n1", description="who killed X",
        status=AssetStatus.PLANTED, created_chapter=1, clues=(cl1, cl2),
    )
    assert len(m.clues) == 2


def test_mystery_add_clue_returns_new():
    m = Mystery(
        id="m1", novel_id="n1", description="x",
        status=AssetStatus.PLANTED, created_chapter=1,
    )
    cl = Clue(id="cl1", mystery_id="m1", description="a", source_chapter=1, source_location="x")
    m2 = m.add_clue(cl)
    assert len(m2.clues) == 1
    assert m2.clues[0] is cl
    assert len(m.clues) == 0  # original unchanged


def test_mystery_related_mystery_field():
    m = Mystery(
        id="m1", novel_id="n1", description="x",
        status=AssetStatus.PLANTED, created_chapter=1,
        related_mystery="m0",
    )
    assert m.related_mystery == "m0"