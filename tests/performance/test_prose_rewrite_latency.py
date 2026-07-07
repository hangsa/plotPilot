"""Phase 2B latency benchmark — P95 < 150ms per chapter (mock LLM)."""
from __future__ import annotations

import time
from dataclasses import dataclass

import pytest

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.fact_guard_service import FactGuardService
from application.sf_log.fact_guard_cpms import build_writing_pipeline_invokers
from application.sf_log.regex_engine import EngineRule, RegexEngine
from domain.sf_log.guard_report import Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


@dataclass
class FakeSnapshot:
    user: str


class FakeAssembler:
    def compile(self, *, spec, variable_plan):                # noqa: ANN001
        return FakeSnapshot(user="")


class FakeProvider:
    def generate(self, _snap):
        # Slightly delayed to simulate LLM call
        time.sleep(0.005)
        return "{}"


class FakeParser:
    def parse(self, text, n):                                 # noqa: ANN001
        return [SFLogRecord(
            log_type="character_emotion",
            params={"subject": "alice", "object": "x"},
            raw="s", chapter_id=1, char_position=0,
        )]


class FakeAudit:
    def append(self, row):
        return -1


@pytest.mark.slow
def test_prose_rewrite_p95_under_150ms():
    rule = EngineRule(
        id="r1", applies_to=None,                            # type: ignore
        severity=Severity.HARD, description="d",
        pattern=".*",
    )
    engine = RegexEngine(rules={"r1": rule})
    bible = ChapterBibleContext(
        chapter_id=1, scene_cast_ids=frozenset(),
        characters=(), worldbuilding_links={},
    )

    audit_repo = FakeAudit()
    invokers = build_writing_pipeline_invokers(
        assembler=FakeAssembler(), llm_provider=FakeProvider(),
        parser_service=FakeParser(), audit_repo=audit_repo,
    )
    svc = FactGuardService(
        engine=engine,
        sflog_invoker=invokers.sflog_invoker,
        prose_invoker=invokers.prose_invoker,
        parse_prose=invokers.parse_prose,
        audit_repo=audit_repo,
    )
    record = SFLogRecord(
        log_type="character_emotion",
        params={"subject": "alice", "object": "x"},
        raw="s", chapter_id=1, char_position=0,
    )

    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        svc.evaluate(
            chapter_text="Alice walked slowly.",
            sflog_records=[record],
            bible_snapshot=bible,
            novel_id="n", chapter_id=1,
        )
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    p95 = latencies[int(0.95 * len(latencies)) - 1]
    assert p95 < 150, f"P95 {p95:.1f}ms >= 150ms target"