"""SFLog 端点：raw 文本查询 + reparse。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_sflog_raw_returns_extracted_tags(client):
    """GET /sflog/raw?chapter=5 → 200 + records/raw_text 字段存在。"""
    resp = client.get("/api/v1/storyos/proj-1/sflog/raw?chapter=5")
    assert resp.status_code == 200
    body = resp.json()
    assert "raw_text" in body
    assert "records" in body
    assert "sf_log_count" in body


def test_sflog_reparse_returns_match_report(client):
    """POST /sflog/reparse/5 → 200 + parsed_count/format_errors/match_report 字段存在。"""
    resp = client.post("/api/v1/storyos/proj-1/sflog/reparse/5")
    assert resp.status_code == 200
    body = resp.json()
    assert "parsed_count" in body
    assert "format_errors" in body
    assert "match_report" in body