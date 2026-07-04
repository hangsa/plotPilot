"""8 registry list endpoint performance benchmark (spec §6.4 < 200ms).

Seeds 50 records per registry into the in-memory adapters that back the
FastAPI CRUD factory, then times a GET on each ``/api/v1/storyos/{project_id}/{asset_type}``
endpoint. In-memory dict storage is expected to respond in single-digit ms
even at 50 records, so the < 200ms target is a generous safety margin.
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from interfaces.main import app
from interfaces.api.v1.storyos.dependencies import (
    reset_conflict_adapter,
    reset_expectation_adapter,
    reset_foreshadowing_adapter,
    reset_goal_adapter,
    reset_mystery_adapter,
    reset_promise_adapter,
    reset_reveal_adapter,
    reset_twist_adapter,
)


SEEDS_PER_REGISTRY = 50
LATENCY_TARGET_MS = 200

# Seed payloads use the actual CreateRequest DTO field names (validated
# against the entity shapes from B1/B2 implementation).
SEED_PAYLOADS: dict[str, dict] = {
    "conflict": {"description": "c", "created_chapter": 1, "intensity": 2},
    "mystery": {"description": "m", "created_chapter": 1},
    "twist": {"description": "t", "created_chapter": 1, "twist_type": "identity_reveal"},
    "promise": {"description": "p", "made_in_chapter": 1, "importance": 2},
    "reveal": {"content": "r", "status": "hidden"},
    "expectation": {"description": "e", "created_chapter": 1, "intensity": 50},
    "goal": {"description": "g", "created_chapter": 1},
    "foreshadowing": {"description": "f", "planted_in_chapter": 1, "importance": 2},
}


@pytest.fixture
def seeded_client():
    """Reset all 8 adapters then seed 50 records each into a fresh project."""
    for reset in (
        reset_conflict_adapter,
        reset_mystery_adapter,
        reset_promise_adapter,
        reset_goal_adapter,
        reset_twist_adapter,
        reset_reveal_adapter,
        reset_expectation_adapter,
        reset_foreshadowing_adapter,
    ):
        reset()

    client = TestClient(app)
    project_id = "perf-test-proj"

    for asset_type, payload in SEED_PAYLOADS.items():
        url = f"/api/v1/storyos/{project_id}/{asset_type}"
        for _ in range(SEEDS_PER_REGISTRY):
            resp = client.post(url, json=payload)
            assert resp.status_code == 201, (
                f"seed POST {asset_type} failed: {resp.status_code} {resp.text}"
            )

    return client, project_id


@pytest.mark.parametrize(
    "asset_type",
    [
        "conflict",
        "mystery",
        "twist",
        "promise",
        "reveal",
        "expectation",
        "goal",
        "foreshadowing",
    ],
)
def test_list_latency_under_200ms(seeded_client, asset_type):
    client, project_id = seeded_client
    url = f"/api/v1/storyos/{project_id}/{asset_type}"
    start = time.perf_counter()
    resp = client.get(url)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert resp.status_code == 200, (
        f"{asset_type} list returned {resp.status_code}: {resp.text}"
    )
    body = resp.json()
    assert body["meta"]["total"] == SEEDS_PER_REGISTRY, (
        f"{asset_type}: expected {SEEDS_PER_REGISTRY} seeded records, "
        f"got {body['meta']['total']}"
    )
    assert elapsed_ms < LATENCY_TARGET_MS, (
        f"{asset_type} list took {elapsed_ms:.1f}ms (target < {LATENCY_TARGET_MS}ms)"
    )


def test_summary_latency_observation(seeded_client):
    """Optional smoke run that records observed latencies for the commit message."""
    client, project_id = seeded_client
    measurements: dict[str, float] = {}
    for asset_type in SEED_PAYLOADS:
        url = f"/api/v1/storyos/{project_id}/{asset_type}"
        start = time.perf_counter()
        resp = client.get(url)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert resp.status_code == 200
        measurements[asset_type] = elapsed_ms

    max_asset, max_ms = max(measurements.items(), key=lambda kv: kv[1])
    summary = "registry list latency ms: " + ", ".join(
        f"{k}={v:.1f}" for k, v in measurements.items()
    )
    pytest.summary = summary  # surfaced by -s output via pytest's terminal capture
    # Sanity: even the slowest registry should stay well under the 200ms cap
    # for an in-memory dict-backed registry.
    assert max_ms < LATENCY_TARGET_MS, (
        f"{max_asset} = {max_ms:.1f}ms exceeds {LATENCY_TARGET_MS}ms"
    )
