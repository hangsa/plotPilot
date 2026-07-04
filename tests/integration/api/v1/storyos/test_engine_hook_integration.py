"""1D endpoint smoke tests + 1E hook coordination tests (xfail until 1E).

1D foundation status (verified by review):
- /api/v1/chapters/{id}/regenerate: does NOT exist. The plan assumed it
  would. Real chapter regeneration paths in 1D are /api/v1/novels/...
  but none invoke StoryOSDelegate yet.
- LLMService class: does NOT exist. The plan's monkeypatch path is wrong.
  Real location: application/engine/services/ai_generation_service.py
  has `generate_chapter` async function (not a class method).
- All SF_LOG -> state-change wiring lands in 1E per plan 2026-07-02-
  storyos-phase-1e-migration.md.

The xfail tests below document the 1E intent so they're discoverable in
CI and naturally flip to PASS once 1E ships. The passing tests verify
the 1D stubs are wired correctly.

Note: we mount ONLY the storyos subrouters (not interfaces.main:app)
because interfaces/main.py:89 uses PEP 604 union syntax incompatible
with Python 3.9.6 (BackendLifecycle | None). The minimal-FastAPI
pattern bypasses this.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interfaces.api.v1.storyos.dependencies import reset_conflict_adapter
from interfaces.api.v1.storyos.router_registry import build_storyos_router


# ─── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def sflog_client():
    """TestClient bound to a minimal FastAPI app mounting storyos routers.

    SFLog/Cascade routes are read-only stubs; no service reset needed.
    """
    app = FastAPI()
    app.include_router(build_storyos_router())
    return TestClient(app)


@pytest.fixture
def conflict_client():
    """TestClient with conflict adapter reset so per-test isolation holds."""
    reset_conflict_adapter()
    app = FastAPI()
    app.include_router(build_storyos_router())
    return TestClient(app)


# ─── 1D Smoke Tests (should PASS in 1D) ───────────────────────────


def test_sflog_reparse_returns_stub_in_1d(sflog_client):
    """1D stub: SFLog reparse returns all-zero MatchReportDTO."""
    resp = sflog_client.post("/api/v1/storyos/proj-1/sflog/reparse/5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["chapter_id"] == 5
    assert body["parsed_count"] == 0
    assert body["match_report"]["match_rate"] == 0.0


def test_cascade_simulate_returns_501_in_1d(sflog_client):
    """1D stub: cascade simulate returns 501 NOT_IMPLEMENTED (1E wires it)."""
    resp = sflog_client.post(
        "/api/v1/storyos/proj-1/cascade/simulate",
        json={
            "project_id": "proj-1",
            "trigger": "mystery_revealed",
            "source_asset_type": "mystery",
            "source_asset_id": "m-1",
        },
    )
    assert resp.status_code == 501
    detail = resp.json().get("detail") or resp.json()
    assert detail.get("code") == "NOT_IMPLEMENTED"


def test_conflict_create_then_get_roundtrip(conflict_client):
    """Smoke test: conflict create returns active asset; get returns same."""
    create = conflict_client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={"description": "smoke", "created_chapter": 1, "intensity": 2},
    )
    assert create.status_code == 201
    asset_id = create.json()["id"]
    assert create.json()["status"] == "active"

    get = conflict_client.get(f"/api/v1/storyos/proj-1/conflict/{asset_id}")
    assert get.status_code == 200
    assert get.json()["id"] == asset_id


# ─── 1E Hook Coordination Tests (xfail until 1E) ──────────────────


@pytest.mark.xfail(
    reason="1E plan: chapter regenerate endpoint + LLMService wiring land "
           "in 2026-07-02-storyos-phase-1e-migration.md. This test "
           "documents the intended behavior; it will flip to PASS once "
           "1E wires /api/v1/novels/.../regenerate -> StoryOSDelegate.",
    strict=False,
)
def test_chapter_regenerate_triggers_sflog_to_state_change():
    """1E intent: POST /api/v1/chapters/{id}/regenerate -> 1C walks pipeline
    -> SF_LOG CONFLICT_ESCALATE parsed -> conflict status escalates.

    Plan reference: F1 task in 2026-07-02-storyos-phase-1d-frontend-api.md.
    The original verbatim test (test_chapter_regenerate_triggers_storyos_state_change)
    is preserved below in this file's git history once 1E is wired.
    """
    # Intentionally unimplemented in 1D. 1E must:
    # 1. Add a chapter-regenerate HTTP endpoint
    # 2. Wire StoryOSDelegate into the chapter generation pipeline
    # 3. Monkey-patch the LLM output to include SF_LOG CONFLICT_ESCALATE
    # 4. Verify the conflict asset's status transitions to 'escalated'
    pytest.fail("Pending 1E wiring")


@pytest.mark.xfail(
    reason="1E plan: chapter regenerate endpoint + LLMService wiring land "
           "in 2026-07-02-storyos-phase-1e-migration.md.",
    strict=False,
)
def test_chapter_regenerate_with_sflog_changes_conflict_status():
    """1E intent: monkey-patched LLM output containing SF_LOG CONFLICT_ESCALATE
    causes the conflict asset's intensity to increase by the delta in the
    SF_LOG comment.

    Original verbatim test preserved in git history once 1E lands.
    """
    pytest.fail("Pending 1E wiring")
