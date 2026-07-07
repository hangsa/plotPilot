"""Regression: Phase 2A fact_guard pass rate on 20-chapter sample (spec §9).

Threshold: 1st-attempt pass rate >= 70% on the sample.
For Phase 2A synthetic clean corpus: expect 100% pass.

NOTE (correction 1): JSON sample stores sflog_records as dicts; the service
expects List[SFLogRecord] (pydantic). We deserialize here.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.fact_guard_service import FactGuardService
from application.sf_log.regex_engine import RegexEngine
from domain.storyos.value_objects.sf_log import SFLogRecord


SAMPLE_PATH = Path(__file__).parent / "fixtures" / "fact_guard_20ch.json"


def test_first_attempt_pass_rate_meets_threshold():
    if not SAMPLE_PATH.exists():
        pytest.skip(f"sample corpus missing: {SAMPLE_PATH}")
    sample = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    assert len(sample) >= 20, f"need >=20 chapters, got {len(sample)}"

    engine = RegexEngine.from_yaml("config/fact_guard_rules.yaml")
    svc = FactGuardService(engine=engine, cpms_invoker=lambda *a, **k: None)

    pass_count = 0
    for ch in sample:
        bible = ChapterBibleContext(
            chapter_id=ch["chapter_number"],
            scene_cast_ids=frozenset(ch.get("scene_cast", [])),
            characters=(),
            worldbuilding_links=ch.get("worldbuilding_links", {}),
        )
        # Deserialize dicts -> SFLogRecord (correction 1)
        records = [SFLogRecord(**r) for r in ch["sflog_records"]]
        report = svc.evaluate(
            chapter_text=ch["text"],
            sflog_records=records,
            bible_snapshot=bible,
        )
        if report.attempt == 1 and report.passed and not report.forced_pass:
            pass_count += 1

    rate = pass_count / len(sample)
    assert rate >= 0.70, f"1st-attempt pass rate {rate:.2%} below 70% threshold"
