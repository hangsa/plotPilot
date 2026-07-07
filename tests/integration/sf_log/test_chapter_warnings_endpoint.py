"""Integration test: GET /{novel_id}/chapters/{chapter_number}/warnings returns fact_guard hits (Phase 2A §7)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from domain.novel.entities.chapter import Chapter
from domain.novel.value_objects.novel_id import NovelId


@pytest.fixture
def client_with_fake_chapter():
    from interfaces.api.v1.core.chapters import router as chapters_router

    app = FastAPI()
    app.include_router(chapters_router)

    fake_chapter = Chapter(
        id="ch-test-001",
        novel_id=NovelId(value="n-test"),
        number=1,
        title="Test",
    )
    fake_chapter.set_warnings([
        {"rule_id": "test.r1", "sflog_id": "raw", "severity": "hard", "message": "bad"},
        {"rule_id": "test.r2", "sflog_id": "raw2", "severity": "soft", "message": "warn"},
    ])

    # Override the repository dependency. Note: get_by_novel_and_number is a
    # concrete method on SqliteChapterRepository, not part of the abstract
    # ChapterRepository interface, so we use a plain MagicMock.
    repo = MagicMock()
    repo.get_by_novel_and_number.return_value = fake_chapter
    app.dependency_overrides = {}
    from interfaces.api.dependencies import get_chapter_repository
    app.dependency_overrides[get_chapter_repository] = lambda: repo

    return TestClient(app), fake_chapter, repo


def test_endpoint_returns_warnings(client_with_fake_chapter):
    client, chapter, _ = client_with_fake_chapter
    resp = client.get(f"/{chapter.novel_id.value}/chapters/{chapter.number}/warnings")
    assert resp.status_code == 200
    body = resp.json()
    assert "warnings" in body
    assert len(body["warnings"]) == 2
    assert body["warnings"][0]["rule_id"] == "test.r1"
    assert body["chapter_id"] == str(chapter.id)


def test_endpoint_returns_404_for_unknown_chapter(client_with_fake_chapter):
    client, _, repo = client_with_fake_chapter
    repo.get_by_novel_and_number.return_value = None
    resp = client.get("/unknown-novel/chapters/999/warnings")
    assert resp.status_code == 404
