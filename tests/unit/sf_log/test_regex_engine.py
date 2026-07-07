"""Unit tests for application/sf_log/regex_engine.py (Phase 2A).

Phase 2A Task 3 — covers 1 rule; full 12-rule coverage in Task 5.
"""
from __future__ import annotations

import pytest

from application.sf_log.regex_engine import RegexEngine, EngineRule
from domain.sf_log.guard_report import Severity
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogParam, SFLogRecord


def _record(log_type: SFLogType, params: dict, chapter_id: int = 1) -> SFLogRecord:
    return SFLogRecord(
        log_type=log_type,
        params=params,
        raw=f"<!-- SF_LOG {log_type.value} " + " ".join(f'{k}="{v}"' for k, v in params.items()) + " -->",
        chapter_id=chapter_id,
        char_position=0,
    )


def test_engine_loads_single_pattern_rule(tmp_path):
    from pathlib import Path

    yaml_path = tmp_path / "rules.yaml"
    yaml_path.write_text(
        "version: 2a-1\n"
        "defaults:\n"
        "  severity_on_miss: hard\n"
        "  text_window_chars: 200\n"
        "rules:\n"
        "  - id: character_emotion.test\n"
        "    applies_to: character_emotion\n"
        "    severity: hard\n"
        "    description: test rule\n"
        "    pattern: '(瞬移|传送)'\n",
        encoding="utf-8",
    )
    engine = RegexEngine.from_yaml(str(yaml_path))
    assert "character_emotion.test" in engine.rules
    rule = engine.rules["character_emotion.test"]
    assert rule.severity is Severity.HARD
    assert rule.applies_to is SFLogType.CHARACTER_EMOTION


def test_engine_evaluates_record_with_negative_match():
    rule = EngineRule(
        id="character_emotion.test",
        applies_to=SFLogType.CHARACTER_EMOTION,
        severity=Severity.SOFT,
        description="test",
        pattern="(瞬移|传送)",
    )
    engine = RegexEngine(rules={"character_emotion.test": rule})
    rec = _record(
        SFLogType.CHARACTER_EMOTION,
        {"character_id": "alice", "level": "1"},
    )
    chapter_text = "alice 缓缓走向窗前。"  # no instant-teleport verb
    hits = engine.evaluate_record(rec, chapter_text)
    assert hits == []  # no match → no hits


def test_engine_evaluates_record_with_positive_match():
    rule = EngineRule(
        id="character_emotion.test",
        applies_to=SFLogType.CHARACTER_EMOTION,
        severity=Severity.HARD,
        description="test",
        pattern="(瞬移|传送)",
        text_window_chars=50,
    )
    engine = RegexEngine(rules={"character_emotion.test": rule})
    rec = _record(
        SFLogType.CHARACTER_EMOTION,
        {"character_id": "alice", "level": "1"},
    )
    chapter_text = "alice 瞬移到了门外。"  # matches the regex ('瞬移' = 2-char compound)
    hits = engine.evaluate_record(rec, chapter_text)
    assert len(hits) == 1
    assert hits[0].rule_id == "character_emotion.test"
    assert hits[0].severity is Severity.HARD
    assert "瞬移" in hits[0].matched_text or "传送" in hits[0].matched_text  # pyright: ignore


def test_engine_skips_rule_not_applicable_to_record_type():
    rule = EngineRule(
        id="character_emotion.test",
        applies_to=SFLogType.CHARACTER_EMOTION,
        severity=Severity.HARD,
        description="test",
        pattern="(瞬移|传送)",
    )
    engine = RegexEngine(rules={"character_emotion.test": rule})
    rec = _record(SFLogType.KNOWLEDGE_GAIN, {"subject": "alice"})
    chapter_text = "他瞬间移动了"
    hits = engine.evaluate_record(rec, chapter_text)
    assert hits == []  # rule's applies_to != rec.log_type → skip
