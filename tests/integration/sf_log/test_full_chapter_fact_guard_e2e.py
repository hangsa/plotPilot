"""E2E test: full chapter run with forbidden verb → fact_guard fires + force-pass at attempt 3 (Phase 2A §5, §6)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from engine.pipeline.base import BaseStoryPipeline
from engine.pipeline.context import PipelineContext
from engine.runtime.storyos_delegate import StoryOSDelegate
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.predeclared import PredeclaredChanges
from domain.storyos.value_objects.sf_log import SFLogRecord


def _make_record() -> SFLogRecord:
    """Location change record that won't trigger no_self_loop / relation / knowledge rules."""
    return SFLogRecord(
        log_type=SFLogType.CHARACTER_LOCATION_CHANGE,
        params={"character_id": "alice", "from": "a", "to": "b"},
        raw='<!-- SF_LOG character_location_change character_id="alice" from="a" to="b" -->',
        chapter_id=1,
        char_position=0,
    )


class _StubLLMProvider:
    """Phase 2B Task 8 fixture: minimal LLM provider stub.

    Empty-string response is treated by the prose_invoker as
    `rollback_signal=True`, which mirrors the Phase 2A stub semantics
    (force-pass at attempt 3). Clean tests pass at attempt 1 without
    ever calling the provider.
    """
    def generate(self, prompt_snapshot):  # noqa: ANN001
        return ""


def test_full_chapter_run_catches_forbidden_verb_and_force_passes():
    """Chapter text with '瞬移' triggers character_location.no_instant_teleport →
    HARD hit → CPMS unavailable → force-pass at attempt 3.

    Asserts: result has fact_guard_report, report.hits contains the rule, attempt=3,
    forced_pass=True, ctx.metadata keys set, storyos_warnings accumulated.
    """
    pipeline = BaseStoryPipeline()
    ctx = PipelineContext(novel_id="n-e2e", chapter_number=1, target_word_count=2000)
    ctx.chapter_content = "alice 瞬移到了门口"  # corrected fixture
    # Phase 2B: wire a stub LLM provider so the pipeline can run.
    ctx.llm_provider = _StubLLMProvider()
    rec = _make_record()

    delegate = MagicMock(spec=StoryOSDelegate)
    parser = MagicMock()
    parser.parse.return_value = [rec]
    parser.validate_format.return_value = []
    parser.match_against_predeclared.return_value = MagicMock(
        missing_changes=[], unexpected_records=[], should_retry=False,
    )
    delegate.parser_service = parser
    ctx.storyos_delegate = delegate

    # Run the Step 5 hook (no need to invoke the full pipeline)
    result = pipeline._hook_step5_post_write_gate(
        ctx, ctx.chapter_content, predeclared=PredeclaredChanges(),
    )

    # Hook return shape
    assert result is not None
    assert "fact_guard_report" in result
    fg = result["fact_guard_report"]
    assert fg is not None

    # fact_guard_report contents
    assert fg.forced_pass is True
    assert fg.attempt == 3  # 3 attempts: HARD hit on each, CPMS returns None
    rule_ids = {h.rule_id for h in fg.hits}
    assert "character_location.no_instant_teleport" in rule_ids

    # ctx.metadata surface
    assert ctx.metadata.get("fact_guard_passed") is True
    assert ctx.metadata.get("fact_guard_forced_pass") is True
    assert ctx.metadata.get("fact_guard_attempt") == 3

    # storyos_warnings accumulated
    warnings = ctx.metadata.get("storyos_warnings", [])
    assert len(warnings) >= 1
    assert any(w["rule_id"] == "character_location.no_instant_teleport" for w in warnings)
    assert all(w["severity"] in ("hard", "soft") for w in warnings)


def test_full_chapter_run_clean_chapter_passes_first_attempt():
    """Chapter with no forbidden verbs, well-formed records → first-attempt pass."""
    pipeline = BaseStoryPipeline()
    ctx = PipelineContext(novel_id="n-clean", chapter_number=1, target_word_count=2000)
    ctx.chapter_content = "alice walked to the door normally."  # English, no forbidden verbs
    # Phase 2B: wire a stub LLM provider (clean path doesn't call it, but
    # the resolver still needs one to avoid NotImplementedError).
    ctx.llm_provider = _StubLLMProvider()
    rec = _make_record()

    delegate = MagicMock(spec=StoryOSDelegate)
    parser = MagicMock()
    parser.parse.return_value = [rec]
    parser.validate_format.return_value = []
    parser.match_against_predeclared.return_value = MagicMock(
        missing_changes=[], unexpected_records=[], should_retry=False,
    )
    delegate.parser_service = parser
    ctx.storyos_delegate = delegate

    result = pipeline._hook_step5_post_write_gate(
        ctx, ctx.chapter_content, predeclared=PredeclaredChanges(),
    )
    assert result is not None
    fg = result["fact_guard_report"]
    assert fg is not None
    assert fg.passed is True
    assert fg.forced_pass is False
    assert fg.attempt == 1
    assert ctx.metadata.get("fact_guard_attempt") == 1