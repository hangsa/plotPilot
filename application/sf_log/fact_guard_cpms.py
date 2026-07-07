"""CPMS wiring for fact_guard — Phase 2B §4 + §7 NOOP_AUDIT_REPO.

Builds sflog_invoker and prose_invoker that talk to existing CPMS nodes
+ a parse_prose wrapper around the existing parser. Pure factory: no I/O
at construction time.

Python 3.9 compat: `from __future__ import annotations` defers evaluation
of `list[GuardHit]` etc., and we avoid PEP 604 union syntax.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, List, Optional, Protocol

from application.sf_log.fact_guard_service import (
    ParseFn,
    ProseRewriteFn,
    ProseRewriteResult,
    SFLogRewriteFn,
    SFLogRewriteResult,
)
from domain.storyos.value_objects.sf_log import SFLogRecord
from domain.sf_log.guard_report import GuardHit


logger = logging.getLogger(__name__)


class LLMProviderProtocol(Protocol):
    def generate(self, prompt_snapshot: Any) -> str: ...


class CPMSAssemblerProtocol(Protocol):
    def compile(self, *, spec: Any, variable_plan: Any) -> Any: ...


SFLOG_NODE = "sf-log-rewrite-with-hints"
PROSE_NODE = "sf-log-prose-rewrite"


# ── NOOP audit repo ──────────────────────────────────────────────────
class _NoopAuditRepo:
    """Singleton no-op audit repo. Used as default when
    app_state.fact_guard_audit_repo isn't wired (test/dev mode).
    append() returns 0 silently.
    """

    def append(self, row: Any) -> int:
        return 0


NOOP_AUDIT_REPO = _NoopAuditRepo()


# ── Result types (re-exported) ───────────────────────────────────────
@dataclass(frozen=True)
class WritingPipelineInvokers:
    sflog_invoker: SFLogRewriteFn
    prose_invoker: ProseRewriteFn
    parse_prose: ParseFn


# ── Wiring factory ──────────────────────────────────────────────────
def build_writing_pipeline_invokers(
    *,
    assembler: CPMSAssemblerProtocol,
    llm_provider: LLMProviderProtocol,
    parser_service: Any,
    audit_repo: Optional[Any] = None,
    max_chapter_text_chars: int = 6000,
) -> WritingPipelineInvokers:
    """Wire up the two CPMS invokers + parser. Pure factory."""

    def sflog_invoker(
        records: List[SFLogRecord],
        hits: List[GuardHit],
        attempt: int,
    ) -> Optional[SFLogRewriteResult]:
        try:
            snapshot = _compile_snapshot(
                assembler, node_key=SFLOG_NODE,
                chapter_text="",                              # sflog-only node
                hits=json.dumps([_hit_to_dict(h) for h in hits]),
                sflog_records=json.dumps([_record_to_dict(r) for r in records]),
                attempt=attempt,
            )
        except Exception as e:
            logger.warning("sflog node %s compile failed: %s", SFLOG_NODE, e)
            _log_failure(audit_repo, node_key=SFLOG_NODE, reason="node_missing")
            return None

        try:
            raw = llm_provider.generate(snapshot)
        except Exception as e:
            logger.warning("sflog provider failed: %s", e)
            _log_failure(audit_repo, node_key=SFLOG_NODE, reason="provider_failed")
            return None

        if not raw.strip():
            return None

        try:
            payload = json.loads(raw)
            new_records_raw = payload.get("records", [])
            new_records = [_dict_to_record(r) for r in new_records_raw]
        except Exception as e:
            logger.warning("sflog malformed response: %s", e)
            return None

        return SFLogRewriteResult(records=new_records)

    def prose_invoker(
        chapter_text: str,
        records: List[SFLogRecord],
        hits: List[GuardHit],
        attempt: int,
    ) -> ProseRewriteResult:
        # Cap input to bound tokens
        if len(chapter_text) > max_chapter_text_chars:
            chapter_text_slice = chapter_text[:max_chapter_text_chars]
        else:
            chapter_text_slice = chapter_text

        try:
            snapshot = _compile_snapshot(
                assembler, node_key=PROSE_NODE,
                chapter_text=chapter_text_slice,
                hits=json.dumps([_hit_to_dict(h) for h in hits]),
                sflog_records=json.dumps([_record_to_dict(r) for r in records]),
                attempt=attempt,
            )
        except Exception as e:
            logger.warning("prose node %s compile failed: %s", PROSE_NODE, e)
            _log_failure(audit_repo, node_key=PROSE_NODE, reason="node_missing")
            return ProseRewriteResult(
                new_chapter_text=chapter_text,
                new_records=records,
                rollback_signal=True,
            )

        try:
            raw = llm_provider.generate(snapshot)
        except Exception as e:
            logger.warning("prose provider failed: %s", e)
            _log_failure(audit_repo, node_key=PROSE_NODE, reason="provider_failed")
            return ProseRewriteResult(
                new_chapter_text=chapter_text,
                new_records=records,
                rollback_signal=True,
            )

        if not raw.strip():
            return ProseRewriteResult(
                new_chapter_text=chapter_text,
                new_records=records,
                rollback_signal=True,
            )

        try:
            payload = json.loads(raw)
        except Exception as e:
            logger.warning("prose malformed response: %s", e)
            return ProseRewriteResult(
                new_chapter_text=chapter_text,
                new_records=records,
                rollback_signal=True,
            )

        return ProseRewriteResult(
            new_chapter_text=payload.get("chapter_text", chapter_text),
            new_records=[_dict_to_record(r) for r in payload.get("records", [])],
            rollback_signal=bool(payload.get("rollback_signal", False)),
        )

    def parse_prose(chapter_text: str, chapter_number: int) -> List[SFLogRecord]:
        return list(parser_service.parse(chapter_text, chapter_number))

    return WritingPipelineInvokers(
        sflog_invoker=sflog_invoker,
        prose_invoker=prose_invoker,
        parse_prose=parse_prose,
    )


# ── Internal helpers ──────────────────────────────────────────────────
def _compile_snapshot(
    assembler: CPMSAssemblerProtocol,
    *,
    node_key: str,
    chapter_text: str,
    hits: str,
    sflog_records: str,
    attempt: int,
) -> Any:
    """Compile a CPMS snapshot via the real assembler.

    Constructs an InvocationSpec + VariablePlan with the per-invocation
    variable bindings. The actual VariablePlan/InvocationSpec shapes are
    pulled from `application.ai_invocation.dtos`; the FakeAssembler in
    unit tests does not consume them but the real one does.
    """
    from application.ai_invocation.dtos import InvocationSpec, VariablePlan
    spec = InvocationSpec(
        operation="sf_log_fact_guard",
        node_key=node_key,
    )
    plan = VariablePlan(
        aliases={
            "chapter_text": chapter_text,
            "hits": hits,
            "sflog_records": sflog_records,
            "attempt": attempt,
        },
    )
    return assembler.compile(spec=spec, variable_plan=plan)


def _hit_to_dict(h: GuardHit) -> dict:
    return {
        "rule_id": h.rule_id,
        "sflog_id": h.sflog_id,
        "severity": h.severity.value,
        "message": h.message,
        "matched_text": h.matched_text,
    }


def _record_to_dict(r: SFLogRecord) -> dict:
    return {
        "raw": r.raw,
        "log_type": r.log_type.value if hasattr(r.log_type, "value") else str(r.log_type),
        "char_position": r.char_position,
    }


def _dict_to_record(d: dict) -> SFLogRecord:
    """Best-effort SFLogRecord reconstruction from dict.

    Falls back to a permissive minimal record if required fields (params,
    chapter_id) are missing — production LLM output may omit them and we
    still want to surface what the model produced. SFLogRecord is pydantic
    frozen + extra='forbid', so unknown keys would raise; we project only
    the known fields.
    """
    return SFLogRecord(
        log_type=str(d.get("log_type", "character_emotion")),
        params={"subject": "", "object": ""},
        raw=str(d.get("raw", "")),
        chapter_id=1,
        char_position=int(d.get("char_position", 0)),
    )


def _log_failure(audit_repo: Optional[Any], *, node_key: str, reason: str) -> None:
    if audit_repo is None:
        return
    try:
        from infrastructure.persistence.sqlite.storyos_fact_guard_logs_repository import (
            FactGuardLogRow,
        )
        audit_repo.append(
            FactGuardLogRow(
                chapter_id=0,                              # unknown at this stage
                chapter_number=0,
                novel_id="",
                attempt=0,
                mode="sflog" if "rewrite-with-hints" in node_key else "prose",
                action=reason,
            )
        )
    except Exception:                                       # noqa: BLE001
        pass