"""Unit tests for application/sf_log/bible_snapshot.py (Phase 2A)."""
from __future__ import annotations

from application.sf_log.bible_snapshot import ChapterBibleContext


def _make_character(char_id: str, name: str = "") -> dict:
    return {"id": char_id, "name": name or char_id}


def test_bible_snapshot_stores_characters_and_links():
    chars = [_make_character("c1"), _make_character("c2")]
    links = {"loc1": ["loc2", "loc3"], "loc2": ["loc1"]}
    ctx = ChapterBibleContext(
        chapter_id=1,
        scene_cast_ids={"c1", "c2"},
        characters=tuple(chars),
        worldbuilding_links=links,
    )
    assert ctx.chapter_id == 1
    assert "c1" in ctx.scene_cast_ids
    assert ctx.worldbuilding_links["loc1"] == ["loc2", "loc3"]


def test_bible_snapshot_scene_cast_membership():
    ctx = ChapterBibleContext(
        chapter_id=2,
        scene_cast_ids={"alice"},
        characters=(_make_character("alice"), _make_character("bob")),
        worldbuilding_links={},
    )
    assert ctx.is_in_scene("alice") is True
    assert ctx.is_in_scene("bob") is False


def test_bible_snapshot_is_frozen_ish():
    ctx = ChapterBibleContext(
        chapter_id=3,
        scene_cast_ids=frozenset(),
        characters=(),
        worldbuilding_links={},
    )
    assert isinstance(ctx.scene_cast_ids, frozenset)


def test_bible_snapshot_is_dataclass_frozen():
    """Spec §2 — bible_snapshot is read-only snapshot at chapter start."""
    from dataclasses import FrozenInstanceError

    ctx = ChapterBibleContext(
        chapter_id=4,
        scene_cast_ids=frozenset(),
        characters=(),
        worldbuilding_links={},
    )
    import pytest
    with pytest.raises(FrozenInstanceError):
        ctx.chapter_id = 999  # type: ignore[misc]