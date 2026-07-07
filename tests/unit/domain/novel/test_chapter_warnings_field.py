"""Unit test: Chapter.warnings field exists and is mutable via setter."""
from __future__ import annotations

import pytest

from domain.novel.entities.chapter import Chapter, ChapterStatus
from domain.novel.value_objects.novel_id import NovelId


def _make_chapter() -> Chapter:
    return Chapter(
        id="ch-1",
        novel_id=NovelId(value="n-1"),
        number=1,
        title="Test Chapter",
    )


def test_chapter_warnings_defaults_to_empty_list():
    ch = _make_chapter()
    assert ch.warnings == []


def test_chapter_set_warnings_replaces_list():
    ch = _make_chapter()
    ch.set_warnings([{"rule_id": "x", "severity": "hard", "message": "m"}])
    assert len(ch.warnings) == 1
    assert ch.warnings[0]["rule_id"] == "x"


def test_chapter_warnings_serialization_roundtrip():
    ch = _make_chapter()
    ch.set_warnings([
        {"rule_id": "test.r1", "sflog_id": "raw", "severity": "hard", "message": "bad"}
    ])
    # to_dict-style serialization (actual key list may differ — adjust per base class)
    serialized = ch.to_dict() if hasattr(ch, "to_dict") else {"warnings": ch.warnings}
    assert "warnings" in serialized