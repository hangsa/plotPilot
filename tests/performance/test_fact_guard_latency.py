"""Performance baseline: fact_guard single-chapter P95 < 100ms (spec §9).

Targets a representative ~3000-char chapter (100 reps of a location-change
prose snippet) evaluated against the full rule set; load the engine ONCE
upfront so the per-iteration timing isolates the evaluate() call.

NOTE (correction 2): `@pytest.mark.slow` (defined in pytest.ini) rather than
`@pytest.mark.performance`; the latter is not registered and `--strict-markers`
would reject it.
"""
from __future__ import annotations

import time

import pytest

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.fact_guard_service import FactGuardService
from application.sf_log.regex_engine import RegexEngine
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


@pytest.mark.slow
def test_fact_guard_p95_under_100ms():
    engine = RegexEngine.from_yaml("config/fact_guard_rules.yaml")
    svc = FactGuardService(engine=engine, cpms_invoker=lambda *a, **k: None)
    bible = ChapterBibleContext(
        chapter_id=1,
        scene_cast_ids=frozenset({"alice"}),
        characters=(),
        worldbuilding_links={"home": ["gate"], "gate": ["home"]},
    )
    records = [
        SFLogRecord(
            log_type=SFLogType.CHARACTER_LOCATION_CHANGE,
            params={"character_id": "alice", "from": "home", "to": "gate"},
            raw='<!-- SF_LOG character_location_change character_id="alice" from="home" to="gate" -->',
            chapter_id=1,
            char_position=0,
        )
    ]
    # ~3000 chars of representative prose
    chapter_text = "alice 走到了门口" * 100

    timings = []
    for _ in range(50):
        start = time.perf_counter()
        svc.evaluate(
            chapter_text=chapter_text,
            sflog_records=records,
            bible_snapshot=bible,
        )
        timings.append(time.perf_counter() - start)

    timings.sort()
    p95_index = int(0.95 * len(timings)) - 1  # 0-indexed sorted index at 95th pct
    p95 = timings[p95_index]
    assert p95 < 0.100, (
        f"P95 {p95 * 1000:.1f}ms exceeds 100ms target "
        f"(n={len(timings)}, median={timings[len(timings) // 2] * 1000:.1f}ms)"
    )
