"""Prose composition strategies for StoryPipeline."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from application.ai_invocation.contracts.autopilot_writing import (
    AUTOPILOT_CHAPTER_PROSE_CONTINUATION,
    AUTOPILOT_CHAPTER_PROSE_OPERATION,
)
from application.ai_invocation.dtos import InvocationSessionStatus
from infrastructure.ai.prompt_keys import CHAPTER_PROSE_GENERATION
from infrastructure.ai.prompt_template_engine import get_template_engine
from engine.runtime.generation_token_policy import CHAPTER_PROSE_MAX_TOKENS


_SFLOG_DIRECTIVE_J2 = (
    Path(__file__).resolve().parents[2]
    / "infrastructure"
    / "ai"
    / "prompt_packages"
    / "nodes"
    / "chapter-prose-generation"
    / "sflog_directive.j2"
)


logger = logging.getLogger(__name__)


StreamSink = Callable[[str], None]
StopChecker = Callable[[], bool]


@dataclass(frozen=True)
class ProseCompositionRequest:
    novel_id: str
    chapter_number: int
    chapter_title: str = ""
    novel_title: str = ""
    genre: str = ""
    outline: str = ""
    context_text: str = ""
    style_guide: str = ""
    target_words: int = 2500
    auto_approve_mode: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)
    stream_sink: StreamSink | None = None
    stop_checker: StopChecker | None = None
    host: Any = None
    llm_service: Any = None


@dataclass(frozen=True)
class ProseCompositionResult:
    content: str = ""
    awaiting_review: bool = False
    session_id: str = ""
    interrupted: bool = False
    status: str = ""


class ProseComposer(Protocol):
    async def compose(self, request: ProseCompositionRequest) -> ProseCompositionResult:
        ...


class ChapterProseInvocationComposer:
    """Compose a whole chapter through the workbench prose CPMS node.

    The composer uses an autopilot-specific operation, so the manual chapter
    projection never bypasses the StoryPipeline save / validate / aftermath
    stages.
    """

    def _build_variables(self, request: ProseCompositionRequest) -> dict[str, Any]:
        metadata = request.metadata or {}
        continuity_context = (
            str(metadata.get("continuity_context") or "").strip()
            or str(request.context_text or "").strip()
        )
        sflog_directive = self._render_sflog_directive(metadata)
        return {
            "target_words": int(request.target_words or 2500),
            "chapter_outline": request.outline,
            "continuity_context": continuity_context,
            "sflog_directive": sflog_directive,
        }

    def _render_sflog_directive(self, metadata: Mapping[str, Any]) -> str:
        """StoryOS tier_0 — 渲染 sflog_directive.j2 注入 LLM 上下文。

        package.yaml 已声明 sflog_directive 变量（type=string, default=''）；
        CPMS 框架会把 explicit_variables['sflog_directive'] 传给 template_engine.render。
        若模板/引擎/文件路径不可用，降级返回空字符串——主流程不受影响。
        """
        if not _SFLOG_DIRECTIVE_J2.is_file():
            return ""
        try:
            template_text = _SFLOG_DIRECTIVE_J2.read_text(encoding="utf-8")
            predeclared_summary = str(
                metadata.get("storyos_predeclared_summary") or "（无）"
            )
            rendered, _missing, _rendered_vars = get_template_engine()._render_template(
                template_text,
                {"predeclared_changes": predeclared_summary},
            )
            return rendered or ""
        except Exception as exc:
            logger.warning(
                "[prose_composer] sflog_directive 渲染失败，回退空字符串: %s", exc,
            )
            return ""

    @staticmethod
    def _max_output_tokens(request: ProseCompositionRequest) -> int:
        return CHAPTER_PROSE_MAX_TOKENS

    @staticmethod
    def _build_config(request: ProseCompositionRequest):
        from domain.ai.services.llm_service import GenerationConfig

        return GenerationConfig(max_tokens=ChapterProseInvocationComposer._max_output_tokens(request), temperature=0.85)

    @staticmethod
    def _load_committed_story_pipeline_content(request: ProseCompositionRequest) -> str:
        """Return accepted prose already committed for this StoryPipeline step.

        StoryPipeline owns the formal chapter save, so its continuation stores
        the accepted text in the invocation commit and then resumes writing.
        On the resumed pipeline tick we must consume that text instead of
        creating another AI invocation for the same chapter.
        """
        try:
            from infrastructure.persistence.database.connection import get_database

            row = get_database().fetch_one(
                """
                SELECT d.accepted_content AS accepted_content
                FROM ai_invocation_sessions s
                JOIN ai_adoption_decisions d ON d.session_id = s.id
                JOIN ai_adoption_commits c ON c.decision_id = d.id
                WHERE s.operation = ?
                  AND s.status = 'completed'
                  AND c.status = 'succeeded'
                  AND json_extract(s.context_json, '$.novel_id') = ?
                  AND CAST(json_extract(s.context_json, '$.chapter_number') AS INTEGER) = ?
                  AND json_extract(s.metadata_json, '$.commit_owner') = 'story_pipeline_save_step'
                ORDER BY c.updated_at DESC, d.accepted_at DESC
                LIMIT 1
                """,
                (
                    AUTOPILOT_CHAPTER_PROSE_OPERATION,
                    request.novel_id,
                    int(request.chapter_number or 0),
                ),
            )
        except Exception:
            return ""
        return str((row or {}).get("accepted_content") or "").strip()

    async def compose(self, request: ProseCompositionRequest) -> ProseCompositionResult:
        from application.ai_invocation.autopilot.factory import get_or_create_autopilot_orchestrator
        from application.ai_invocation.autopilot.intents import AutopilotInvocationIntent
        from application.ai_invocation.autopilot.policy import AutopilotInvocationPolicyResolver
        from application.ai_invocation.contracts import ensure_invocation_contract
        from infrastructure.persistence.database.connection import get_database

        committed_content = self._load_committed_story_pipeline_content(request)
        if committed_content:
            if request.stream_sink:
                request.stream_sink(committed_content)
            return ProseCompositionResult(
                content=committed_content,
                status="committed_story_pipeline_content",
            )

        db = get_database()
        ensure_invocation_contract(AUTOPILOT_CHAPTER_PROSE_OPERATION, CHAPTER_PROSE_GENERATION, db)
        context = {
            "novel_id": request.novel_id,
            "chapter_number": request.chapter_number,
            "beat_index": 0,
        }
        policy = AutopilotInvocationPolicyResolver().resolve(
            operation=AUTOPILOT_CHAPTER_PROSE_OPERATION,
            node_key=CHAPTER_PROSE_GENERATION,
            novel=type("StoryPipelinePolicy", (), {"auto_approve_mode": request.auto_approve_mode})(),
            context=context,
        )
        intent = AutopilotInvocationIntent(
            novel_id=request.novel_id,
            stage="writing",
            operation=AUTOPILOT_CHAPTER_PROSE_OPERATION,
            node_key=CHAPTER_PROSE_GENERATION,
            context=context,
            explicit_variables=self._build_variables(request),
            continuation_handler_key=AUTOPILOT_CHAPTER_PROSE_CONTINUATION,
            policy_hint=policy,
            metadata={
                "source": "story_pipeline.chapter_prose_composer",
                "target_words": request.target_words,
                "generation_mode": "full_chapter_once",
                "commit_owner": "story_pipeline_save_step",
            },
            config={"max_tokens": self._max_output_tokens(request), "temperature": 0.85},
        )
        host = request.host or type("StoryPipelineComposerHost", (), {"llm_service": request.llm_service})()
        orchestrator = get_or_create_autopilot_orchestrator(host)
        prepared = await orchestrator.prepare(intent)
        if prepared.session.status in {
            InvocationSessionStatus.AWAITING_PRE_CALL_REVIEW,
            InvocationSessionStatus.BLOCKED,
        }:
            return ProseCompositionResult(
                awaiting_review=True,
                session_id=prepared.session.id,
            )

        stop_seen = False

        def _on_chunk(chunk: str, full: str):
            nonlocal stop_seen
            if request.stop_checker and request.stop_checker():
                stop_seen = True
                return False
            if request.stream_sink:
                request.stream_sink(full)
            return True

        outcome = await orchestrator.generate_prepared_streaming(
            intent=intent,
            prepared_result=prepared,
            config=self._build_config(request),
            on_chunk=_on_chunk,
        )
        return ProseCompositionResult(
            content=outcome.accepted_content or "",
            session_id=outcome.session_id,
            interrupted=stop_seen or outcome.status == "cancelled" or outcome.next_action == "cancelled",
            status=outcome.status,
        )
