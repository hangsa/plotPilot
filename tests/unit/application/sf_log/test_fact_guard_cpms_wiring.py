"""Tests for fact_guard_cpms.build_writing_pipeline_invokers (Phase 2B Task 6)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List

import pytest

from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


def _record(raw: str = "sf1", log_type: str = "character_emotion",
            char_position: int = 0, chapter_id: int = 1) -> SFLogRecord:
    """Helper — SFLogRecord pydantic model requires params + chapter_id."""
    try:
        resolved = SFLogType(log_type)
    except ValueError:
        resolved = SFLogType[log_type]
    return SFLogRecord(
        log_type=resolved,
        params={"subject": "alice", "object": "x"},
        raw=raw,
        chapter_id=chapter_id,
        char_position=char_position,
    )


@dataclass
class FakeSnapshot:
    system: str
    user: str


class FakeAssembler:
    """Stub assembler that returns a FakeSnapshot for any node_key."""

    def __init__(self, by_node: dict):
        self._by_node = by_node

    def compile(self, *, spec: Any, variable_plan: Any) -> FakeSnapshot:   # noqa: ANN001
        if spec.node_key not in self._by_node:
            raise KeyError(f"no snapshot for {spec.node_key}")
        snap = self._by_node[spec.node_key]
        return FakeSnapshot(system=snap["system"], user=snap["user"])


class FakeProvider:
    """Scripted responses — returns predetermined strings for each call."""

    def __init__(self, scripts: List[str]):
        self._scripts = list(scripts)
        self.calls: List[FakeSnapshot] = []

    def generate(self, snapshot: Any) -> str:
        self.calls.append(snapshot)
        if not self._scripts:
            return "[]"
        return self._scripts.pop(0)


class FakeParser:
    """Stub parser_service.parse — returns predetermined records."""

    def __init__(self, scripts: List[List]):
        self._scripts = list(scripts)
        self.calls: List[str] = []

    def parse(self, text: str, chapter_number: int) -> List[SFLogRecord]:  # noqa: ANN001
        self.calls.append(text)
        if not self._scripts:
            return []
        return self._scripts.pop(0)


from application.sf_log.fact_guard_cpms import (   # noqa: E402
    SFLOG_NODE,
    PROSE_NODE,
    build_writing_pipeline_invokers,
    NOOP_AUDIT_REPO,
)


class TestNodeRouting:
    def test_sflog_node_key(self):
        assert SFLOG_NODE == "sf-log-rewrite-with-hints"

    def test_prose_node_key(self):
        assert PROSE_NODE == "sf-log-prose-rewrite"


class TestSflogInvoker:
    def test_sflog_invoker_returns_records(self):
        asm = FakeAssembler({
            SFLOG_NODE: {"system": "sys", "user": "user {{chapter_text}}"},
        })
        provider = FakeProvider([
            json.dumps({"records": [{"raw": "sf1", "log_type": "character_emotion",
                                     "char_position": 0}]}),
        ])
        parser = FakeParser([])
        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider, parser_service=parser,
        )
        result = invokers.sflog_invoker(
            records=[_record(raw="old")],
            hits=[], attempt=1,
        )
        assert result is not None
        assert len(result.records) == 1
        assert result.records[0].raw == "sf1"

    def test_sflog_invoker_returns_none_on_malformed_json(self):
        asm = FakeAssembler({SFLOG_NODE: {"system": "", "user": ""}})
        provider = FakeProvider(["not json"])
        parser = FakeParser([])
        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider, parser_service=parser,
        )
        result = invokers.sflog_invoker(records=[], hits=[], attempt=1)
        assert result is None


class TestProseInvoker:
    def test_prose_invoker_returns_prose_rewrite_result(self):
        asm = FakeAssembler({PROSE_NODE: {"system": "", "user": ""}})
        rewritten_text = "The new chapter prose"
        provider = FakeProvider([
            json.dumps({
                "chapter_text": rewritten_text,
                "notes": "fixed sentence 1",
                "rollback_signal": False,
            }),
        ])
        parser = FakeParser([])
        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider, parser_service=parser,
        )
        result = invokers.prose_invoker(
            chapter_text="OLD", records=[], hits=[], attempt=3,
        )
        assert result.new_chapter_text == rewritten_text
        assert result.rollback_signal is False

    def test_prose_invoker_rollback_signal_passthrough(self):
        asm = FakeAssembler({PROSE_NODE: {"system": "", "user": ""}})
        provider = FakeProvider([
            json.dumps({
                "chapter_text": "ORIGINAL",
                "notes": "REQUIRES_PROSE_ROLLBACK",
                "rollback_signal": True,
            }),
        ])
        parser = FakeParser([])
        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider, parser_service=parser,
        )
        result = invokers.prose_invoker(
            chapter_text="ORIGINAL", records=[], hits=[], attempt=3,
        )
        assert result.rollback_signal is True


class TestParseProse:
    def test_parse_prose_delegates(self):
        expected = [_record(raw="r")]
        asm = FakeAssembler({})
        provider = FakeProvider([])
        parser = FakeParser([expected])
        invokers = build_writing_pipeline_invokers(
            assembler=asm, llm_provider=provider, parser_service=parser,
        )
        actual = invokers.parse_prose("some text", 7)
        assert actual == expected


class TestNoopAuditRepo:
    def test_noop_audit_repo_returns_zero(self):
        from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
            FactGuardLogRow,
        )
        result = NOOP_AUDIT_REPO.append(
            FactGuardLogRow(
                chapter_id=1, chapter_number=1, novel_id="n",
                attempt=1, mode="sflog", action="passed",
            )
        )
        assert result == 0