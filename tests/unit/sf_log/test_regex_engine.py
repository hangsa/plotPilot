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


# ---------------------------------------------------------------------------
# Phase 2A Task 4 — python_callable escape hatch + multi-pattern YAML
# ---------------------------------------------------------------------------

from application.sf_log.bible_snapshot import ChapterBibleContext
from application.sf_log.callables import (
    KNOWLEDGE_OMNISCIENCE,
    LOCATION_CONTINUITY,
    MYSTERY_REVEAL_WINDOW,
)


def test_engine_dispatches_to_python_callable_for_matching_rule():
    """Rule 6 (knowledge_omniscience) uses python_callable, not pattern."""
    rule = EngineRule(
        id="knowledge_gain.no_omniscience",
        applies_to=SFLogType.KNOWLEDGE_GAIN,
        severity=Severity.HARD,
        description="grantor must be in scene.cast",
        python_callable="application.sf_log.callables.knowledge_omniscience.evaluate",
    )
    engine = RegexEngine(rules={rule.id: rule})
    rec = _record(
        SFLogType.KNOWLEDGE_GAIN,
        {"subject": "alice", "object": "secret"},
    )
    bible = ChapterBibleContext(
        chapter_id=1,
        scene_cast_ids=frozenset({"bob"}),  # alice not in scene
        characters=(),
        worldbuilding_links={},
    )
    hits = engine.evaluate_record(rec, "任意文本", bible_snapshot=bible)
    assert len(hits) == 1
    assert hits[0].rule_id == "knowledge_gain.no_omniscience"


def test_engine_skips_python_callable_when_bible_snapshot_missing():
    rule = EngineRule(
        id="knowledge_gain.no_omniscience",
        applies_to=SFLogType.KNOWLEDGE_GAIN,
        severity=Severity.HARD,
        description="x",
        python_callable="x.y",
    )
    engine = RegexEngine(rules={rule.id: rule})
    rec = _record(SFLogType.KNOWLEDGE_GAIN, {"subject": "alice"})
    hits = engine.evaluate_record(rec, "x")
    assert hits == []  # no bible → can't evaluate


def test_engine_multi_patterns_or_semantics(tmp_path):
    from pathlib import Path

    yaml_path = tmp_path / "rules.yaml"
    yaml_path.write_text(
        "version: 2a-1\n"
        "defaults:\n"
        "  severity_on_miss: hard\n"
        "  text_window_chars: 200\n"
        "rules:\n"
        "  - id: character_location.test\n"
        "    applies_to: character_location_change\n"
        "    severity: hard\n"
        "    description: test\n"
        "    patterns:\n"
        "      - name: forbidden_verbs\n"
        "        regex: '(瞬移|传送|闪现)'\n",
        encoding="utf-8",
    )
    engine = RegexEngine.from_yaml(str(yaml_path))
    rule = engine.rules["character_location.test"]
    rec = _record(
        SFLogType.CHARACTER_LOCATION_CHANGE,
        {"character_id": "x", "from": "a", "to": "b"},
    )
    # Fixture fix: '他瞬移到了' contains '瞬移' which matches the YAML pattern.
    # The plan-bug-discovered-again fixture '他瞬间移动到房间' would NOT match.
    hits = engine.evaluate_record(rec, "他瞬移到了")
    assert len(hits) == 1


class TestKnowledgeOmniscience:
    def test_returns_hit_when_grantor_not_in_scene(self):
        bible = ChapterBibleContext(
            chapter_id=1,
            scene_cast_ids=frozenset({"bob"}),
            characters=(),
            worldbuilding_links={},
        )
        rec = _record(SFLogType.KNOWLEDGE_GAIN, {"subject": "alice", "object": "x"})
        hits = KNOWLEDGE_OMNISCIENCE(rec, bible)
        assert len(hits) == 1
        assert hits[0].severity is Severity.HARD

    def test_returns_no_hit_when_grantor_in_scene(self):
        bible = ChapterBibleContext(
            chapter_id=1,
            scene_cast_ids=frozenset({"alice"}),
            characters=(),
            worldbuilding_links={},
        )
        rec = _record(SFLogType.KNOWLEDGE_GAIN, {"subject": "alice", "object": "x"})
        assert KNOWLEDGE_OMNISCIENCE(rec, bible) == []


class TestLocationContinuity:
    def test_returns_hit_when_two_locations_disconnected(self):
        bible = ChapterBibleContext(
            chapter_id=1,
            scene_cast_ids=frozenset(),
            characters=(),
            worldbuilding_links={"loc_a": ["loc_b"], "loc_b": ["loc_a"]},
            # loc_c disconnected from {loc_a, loc_b}
        )
        records = [
            _record(
                SFLogType.CHARACTER_LOCATION_CHANGE,
                {"character_id": "x", "to": "loc_a"},
            ),
            _record(
                SFLogType.CHARACTER_LOCATION_CHANGE,
                {"character_id": "x", "to": "loc_c"},
            ),
        ]
        result = LOCATION_CONTINUITY(records, bible)
        assert len(result) >= 1


class TestMysteryRevealWindow:
    def test_returns_no_hit_when_mystery_id_reference_is_valid_format(self):
        """Phase 2A: only check mystery_id is well-formed (alnum + dash + underscore);
        stricter paid-window check pushes to Phase 2B per spec §11."""
        bible = ChapterBibleContext(
            chapter_id=1,
            scene_cast_ids=frozenset(),
            characters=(),
            worldbuilding_links={},
        )
        rec = _record(
            SFLogType.MYSTERY_CLUE,
            {"mystery_id": "mystery-001", "clue_id": "c1"},
        )
        hits = MYSTERY_REVEAL_WINDOW(rec, bible)
        assert hits == []  # well-formed mystery_id → no hit


# ---------------------------------------------------------------------------
# Phase 2A Task 5 — full 12-rule YAML + chapter-level evaluate_chapter
# ---------------------------------------------------------------------------

import pytest  # noqa: E402


@pytest.fixture
def full_engine():
    """Loads the real config/fact_guard_rules.yaml (12 rules)."""
    from pathlib import Path

    yaml_path = (
        Path(__file__).parent.parent.parent.parent
        / "config"
        / "fact_guard_rules.yaml"
    )
    return RegexEngine.from_yaml(str(yaml_path))


@pytest.mark.parametrize("rule_id,expected_severity", [
    ("character_relation.no_self_loop", "hard"),
    ("character_location.no_instant_teleport", "hard"),
    ("character_location.continuity", "hard"),
    ("character_physical.no_undo_without_cause", "hard"),
    ("character_emotion.amplitude_cap", "soft"),
    ("knowledge_gain.no_omniscience", "hard"),
    ("conflict_escalate.no_repeat", "soft"),
    ("mystery_clue.no_premature_reveal", "hard"),
    ("twist_reveal.no_orphan", "hard"),
    ("expectation_fulfill.scope", "soft"),
    ("goal_milestone.no_skip", "hard"),
    ("registry_create.uniqueness", "hard"),
])
def test_all_12_rules_present(full_engine, rule_id, expected_severity):
    assert rule_id in full_engine.rules
    assert full_engine.rules[rule_id].severity.value == expected_severity


def test_evaluate_chapter_dispatches_to_python_callable_rules(full_engine):
    """evaluate_chapter routes KNOWLEDGE_GAIN records to rule 6 callable."""
    bible = ChapterBibleContext(
        chapter_id=1,
        scene_cast_ids=frozenset({"bob"}),
        characters=(),
        worldbuilding_links={},
    )
    record = _record(SFLogType.KNOWLEDGE_GAIN, {"subject": "alice", "object": "x"})
    hits = full_engine.evaluate_chapter(
        [record], "any text", bible_snapshot=bible
    )
    assert any(h.rule_id == "knowledge_gain.no_omniscience" for h in hits)


def test_evaluate_chapter_runs_pattern_rules(full_engine):
    record = _record(
        SFLogType.CHARACTER_LOCATION_CHANGE,
        {"character_id": "x", "to": "y"},
    )
    # Fixture fix: '瞬移' (2 chars) matches `(瞬移|传送|闪现)`; '瞬间移动' would NOT.
    chapter_text = "他瞬移到了"
    hits = full_engine.evaluate_chapter([record], chapter_text)
    assert any(h.rule_id == "character_location.no_instant_teleport" for h in hits)


# ---------------------------------------------------------------------------
# Phase 2A Task 5 — relation_no_self_loop callable (Rule 1)
# ---------------------------------------------------------------------------

from application.sf_log.callables.relation_no_self_loop import (  # noqa: E402
    evaluate as _relation_no_self_loop,
)


class TestRelationNoSelfLoop:
    def test_returns_hit_when_subject_equals_object(self):
        bible = ChapterBibleContext(
            chapter_id=1,
            scene_cast_ids=frozenset(),
            characters=(),
            worldbuilding_links={},
        )
        rec = _record(
            SFLogType.CHARACTER_RELATION_CHANGE,
            {"subject": "alice", "object": "alice"},
        )
        hits = _relation_no_self_loop(rec, bible)
        assert len(hits) == 1
        assert hits[0].rule_id == "character_relation.no_self_loop"
        assert hits[0].severity is Severity.HARD

    def test_returns_no_hit_when_subject_differs_from_object(self):
        bible = ChapterBibleContext(
            chapter_id=1,
            scene_cast_ids=frozenset(),
            characters=(),
            worldbuilding_links={},
        )
        rec = _record(
            SFLogType.CHARACTER_RELATION_CHANGE,
            {"subject": "alice", "object": "bob"},
        )
        assert _relation_no_self_loop(rec, bible) == []
