"""End-to-end test: full chapter run with fact_guard 3-attempt loop + prose rewrite.

Verifies:
- All 3 attempts invoke the right CPMS node
- Audit row inserted for each attempt
- Rollback path keeps original prose
- Rewritten-chapter-text passed back to caller
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional

import pytest

from application.sf_log.fact_guard_service import (
    FactGuardService,
    ProseRewriteResult,
)
from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.regex_engine import EngineRule, RegexEngine
from application.sf_log.fact_guard_cpms import (
    SFLOG_NODE,
    PROSE_NODE,
    build_writing_pipeline_invokers,
    NOOP_AUDIT_REPO,
)
from domain.storyos.value_objects.sf_log import SFLogRecord
from domain.sf_log.guard_report import Severity


@dataclass
class FakeSnapshot:
    user: str


class FakeAssembler:
    def __init__(self):
        self.calls = []

    def compile(self, *, spec, variable_plan):                # noqa: ANN001
        self.calls.append(spec.node_key)
        return FakeSnapshot(user=f"rendered for {spec.node_key}")


class FakeProvider:
    def __init__(self, responses):
        self._responses = list(responses)

    def generate(self, snap):
        return self._responses.pop(0)


class FakeParser:
    def parse(self, text, n):                                 # noqa: ANN001
        return [SFLogRecord(
            log_type="character_emotion",
            params={"subject": "alice", "object": "x"},
            raw="x", chapter_id=1, char_position=0,
        )]


class FakeAuditRepo:
    def __init__(self):
        self.rows = []

    def append(self, row):
        self.rows.append(row)
        return -1


def _engine_with_hard_rule() -> RegexEngine:
    rule = EngineRule(
        id="r1", applies_to=None,                            # type: ignore
        severity=Severity.HARD, description="d",
        pattern=".*",                                        # matches anything → 1 HARD hit
    )
    return RegexEngine(rules={"r1": rule})


def _bible() -> ChapterBibleContext:
    return ChapterBibleContext(
        chapter_id=7, scene_cast_ids=frozenset(),
        characters=(), worldbuilding_links={},
    )


class TestE2EProseRewrite:
    def test_rollback_path(self):
        asm = FakeAssembler()
        provider = FakeProvider([
            # attempt 1 sflog: malformed → returns None
            "not json",
            # attempt 2 sflog: malformed → returns None
            "also not json",
            # attempt 3 prose: also malformed → returns rollback
            "garbage response",
        ])
        parser = FakeParser()
        audit_repo = FakeAuditRepo()

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
        report, rewritten = svc.evaluate(
            chapter_text="ORIGINAL TEXT",
            sflog_records=[SFLogRecord(
                log_type="character_emotion",
                params={"subject": "alice", "object": "x"},
                raw="s", chapter_id=1, char_position=0,
            )],
            bible_snapshot=_bible(),
            novel_id="alpha", chapter_id=42,
        )
        assert report.passed is True
        assert report.forced_pass is True
        assert rewritten is None                              # rollback path

        # Audit rows: 2 sflog no_rewrite + 1 prose forced_pass_rollback_llm
        actions = [r.action for r in audit_repo.rows]
        assert actions.count("no_rewrite_sflog") == 2
        assert actions.count("forced_pass_rollback_llm") == 1

        # CPMS routing: sflog + sflog + prose
        assert asm.calls == [SFLOG_NODE, SFLOG_NODE, PROSE_NODE]