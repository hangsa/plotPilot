"""5-chapter corpus exercising 3 modes:
1. auto-pass (zero HARD hits after attempt 1)
2. sflog-rewritten (LLM returns new records, attempt 2 clears hits)
3. prose-rewritten (LLM rewrites prose, attempt 3 keeps rewrite)
4. prose-rewritten + rollback candidate (LLM rewrites but regression -> rollback)
5. provider_failed (LLM throws -> rollback, force_pass)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.fact_guard_service import FactGuardService
from application.sf_log.fact_guard_cpms import build_writing_pipeline_invokers
from application.sf_log.regex_engine import EngineRule, RegexEngine
from domain.sf_log.guard_report import Severity
from domain.storyos.value_objects.sf_log import SFLogRecord


FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "fact_guard_5ch_prose.json"
)


@dataclass
class FakeSnapshot:
    user: str


class FakeAssembler:
    def compile(self, *, spec, variable_plan):                # noqa: ANN001
        return FakeSnapshot(user=spec.node_key)


def _engine_with_hard_rule() -> RegexEngine:
    rule = EngineRule(
        id="r1", applies_to=None,                            # type: ignore
        severity=Severity.HARD, description="d",
        pattern=".*",                                        # matches anything -> 1 HARD hit
    )
    return RegexEngine(rules={"r1": rule})


def _bible(chapter_id: int = 1) -> ChapterBibleContext:
    return ChapterBibleContext(
        chapter_id=chapter_id, scene_cast_ids=frozenset(),
        characters=(), worldbuilding_links={},
    )


class _FakeProvider:
    def __init__(self, scripts):
        self._scripts = list(scripts)

    def generate(self, _snap):
        if not self._scripts:
            return "{}"
        v = self._scripts.pop(0)
        if isinstance(v, Exception):
            raise v
        return v


class _FakeParser:
    def parse(self, text, n):                                 # noqa: ANN001
        return [SFLogRecord(
            log_type="character_emotion",
            params={"subject": "alice", "object": "x"},
            raw="s", chapter_id=1, char_position=0,
        )]


class _FakeAudit:
    def __init__(self):
        self.rows = []

    def append(self, row):
        self.rows.append(row)
        return -1


def test_5ch_corpus_pass_rate_at_least_80_percent():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    chapters = fixture["chapters"]
    passing = 0
    for ch in chapters:
        asm = FakeAssembler()
        provider = _FakeProvider(ch["provider_responses"])
        parser = _FakeParser()
        audit_repo = _FakeAudit()

        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider,
            parser_service=parser, audit_repo=audit_repo,
        )
        svc = FactGuardService(
            engine=_engine_with_hard_rule(),
            sflog_invoker=invokers.sflog_invoker,
            prose_invoker=invokers.prose_invoker,
            parse_prose=invokers.parse_prose,
            audit_repo=audit_repo,
        )
        records = [SFLogRecord(**r) for r in ch.get("sflog_records", [])]
        report, rewritten = svc.evaluate(
            chapter_text=ch["chapter_text"],
            sflog_records=records,
            bible_snapshot=_bible(ch["chapter_number"]),
            novel_id=ch["novel_id"], chapter_id=ch["chapter_id"],
        )
        if ch["expected_pass"]:
            if report.passed and (ch.get("expected_attempt") is None
                                   or report.attempt == ch["expected_attempt"]):
                passing += 1

    ratio = passing / len(chapters)
    assert ratio >= 0.80, f"pass rate {ratio:.0%} < 80%"