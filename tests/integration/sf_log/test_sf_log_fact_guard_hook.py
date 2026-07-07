"""Integration test: fact_guard evaluates inside Step 5 hook after parse + match (Phase 2A §6)."""
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
    # Use CHARACTER_RELATION_CHANGE with distinct subject/object so rule 1
    # (no_self_loop python_callable) does NOT fire. With empty bible scene_cast
    # AND no CHAPTER_LOCATION_CHANGE records, the rule python_callable doesn't
    # apply. So this record will pass fact_guard cleanly on attempt 1.
    return SFLogRecord(
        log_type=SFLogType.CHARACTER_RELATION_CHANGE,
        params={"subject": "alice", "object": "bob"},
        raw='<!-- SF_LOG character_relation_change subject="alice" object="bob" -->',
        chapter_id=1,
        char_position=0,
    )


class _StubLLMProvider:
    """Phase 2B Task 8 fixture: minimal LLM provider stub.

    Returns an empty string — the prose_invoker in fact_guard_cpms treats
    empty responses as `rollback_signal=True`, which mirrors the Phase 2A
    stub semantics (force-pass on attempt 3). Tests that don't hit HARD
    rules (clean chapter) pass on attempt 1 without ever calling the
    provider.
    """
    def generate(self, prompt_snapshot):  # noqa: ANN001
        return ""


@pytest.fixture
def pipeline_and_ctx():
    pipeline = BaseStoryPipeline()
    ctx = PipelineContext(novel_id="n-1", chapter_number=1)
    # Phase 2B: wire a stub LLM provider on ctx so the pipeline can run
    # the 3-attempt loop (otherwise NotImplementedError from
    # _resolve_fact_guard_provider).
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
    return pipeline, ctx, rec


def test_hook_returns_fact_guard_report_in_result(pipeline_and_ctx):
    """After Phase 2A embed, hook return must include `fact_guard_report` key."""
    pipeline, ctx, _ = pipeline_and_ctx
    # CHARACTER_RELATION_CHANGE record with distinct subject/object → no HARD hit
    # → passed=True, forced_pass=False, attempt=1.
    result = pipeline._hook_step5_post_write_gate(
        ctx, "any text", predeclared=PredeclaredChanges(),
    )
    assert result is not None
    assert "fact_guard_report" in result
    fg = result["fact_guard_report"]
    assert fg is not None
    assert fg.passed is True
    assert fg.forced_pass is False
    assert fg.attempt == 1
    # Verify ctx.metadata got the expected keys
    assert ctx.metadata.get("fact_guard_passed") is True
    assert ctx.metadata.get("fact_guard_forced_pass") is False
    assert ctx.metadata.get("fact_guard_attempt") == 1


def test_hook_force_pass_after_three_attempts(pipeline_and_ctx):
    """Chapter text with forbidden verb (瞬移) → HARD hit → CPMS unavailable → force-pass at 3."""
    pipeline, ctx, _ = pipeline_and_ctx
    # Test record is KNOWLEDGE_GAIN — but character_location rule applies to
    # CHARACTER_LOCATION_CHANGE records. Use the latter to trigger HARD hit on 瞬移.
    ctx.storyos_delegate.parser_service.parse.return_value = [
        SFLogRecord(
            log_type=SFLogType.CHARACTER_LOCATION_CHANGE,
            params={"character_id": "alice", "from": "a", "to": "b"},
            raw='<!-- SF_LOG character_location_change character_id="alice" from="a" to="b" -->',
            chapter_id=1,
            char_position=0,
        )
    ]
    result = pipeline._hook_step5_post_write_gate(
        ctx, "他瞬移到了门外", predeclared=PredeclaredChanges(),
    )
    assert result is not None
    fg = result["fact_guard_report"]
    assert fg is not None
    assert fg.forced_pass is True
    assert fg.attempt == 3
