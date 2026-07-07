# Phase 2B — Tier 0 SF_LOG Prose Rewrite (v1.4) — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend Phase 2A's Tier 0 SF_LOG fact_guard with paragraph-level prose rewrite so contradictions between SF_LOG records and chapter prose are auto-fixed (or rolled back if the rewrite increases hard-hit count), with full audit logging.

**Architecture:** Two CPMS prompt packages (`sf-log-rewrite-with-hints` for SF_LOG-only mode, `sf-log-prose-rewrite` for prose-mode). A 3-attempt loop with auto-escalation: attempts 1+2 call the SF_LOG-only invoker, attempt 3 calls the prose invoker with a regression guard. New SQLite audit table `storyos_fact_guard_logs` records every iteration so a Phase 2C review UI can surface LLM activity to writers. Audit failures never crash the pipeline (graceful degradation).

**Tech Stack:** Python 3.9.6, SQLite, FastAPI, existing CPMS assembler pipeline, existing pipeline hook system.

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Step 5 hook (_hook_step5_post_write_gate)                                  │
│  base.py:1359-1453 — current 2A site                                         │
│                                                                              │
│   parse(text)  ──►  records                                                  │
│                          │                                                   │
│                          ▼                                                   │
│   ┌────────────────────────────────────────────────┐                         │
│   │  FactGuardService.evaluate(text, records, …)   │  ← Phase 2B refactor    │
│   │                                                │                         │
│   │  attempt 1 ─► SF_LOG-mode eval                 │                         │
│   │       hard? ─► sflog_invoker(records, …) → records_v2                   │
│   │  attempt 2 ─► SF_LOG-mode eval (records_v2)    │                         │
│   │       hard? ─► sflog_invoker(records_v2, …) → records_v3                │
│   │  attempt 3 ─► PROSE-mode eval (records_v3)     │                         │
│   │       hard? ─► prose_invoker(text, records_v3, …) → text_v2, records_v4 │
│   │             ─► re-parse(text_v2), re-eval                                   │
│   │             ─► hard_after ≤ hard_before ? keep : rollback (text/records_v3)│
│   │  still hard? ─► force_pass, log to storyos_fact_guard_logs               │
│   └────────────────────────────────────────────────┘                         │
│                                                                              │
│   build_writing_pipeline_invokers() injects:                                 │
│     - sflog_invoker   → CPMS node `sf-log-rewrite-with-hints` (existing)     │
│     - prose_invoker   → CPMS node `sf-log-prose-rewrite`      (NEW 2B)       │
│     - prose parser    → delegate.parser_service.parse                       │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                     storyos_fact_guard_logs (SQLite table — NEW)
                       id, chapter_id, chapter_number, attempt, mode, action,
                       rule_id, severity, hard_before, hard_after,
                       diff_excerpt, notes, created_at
```

5 cooperating subsystems (matching the engine's existing 5-subsystem mental model):
1. **Narrative State Machine** — chapter text unchanged on rollback; only successful prose rewrite mutates text.
2. **Vector Retrieval Layer** — unaffected; not in scope for prose rewrite.
3. **Engine Runtime** — same `_hook_step5_post_write_gate`; new audit logging path; rewritten text plumbed into Step 6's save.
4. **Prompt Strategy Layer** — 2 CPMS nodes (sflog + prose), one FactGuardService-mediated seam.
5. **Quality Monitor** — extended with HARD-hit regression guard at attempt 3; new audit table backs review UI in 2C.

---

## 2. Files & CPMS node internals

### New files (5)

| Path | Responsibility |
|------|----------------|
| `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/package.yaml` | CPMS manifest for the new prose node. `category: rewrite`, `sort_order: 116`, builtin. |
| `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/user.md` | Prose-rewrite prompt (different persona from sflog — see below). |
| `infrastructure/ai/prompt_packages/nodes/sf-log-prose-rewrite/system.md` | Optional system prompt (sister to user.md; same structure as other rewrite nodes). |
| `application/sf_log/fact_guard_cpms.py` | Wiring helper. `build_writing_pipeline_invokers(provider, parser, novel_id_resolver)` returns a typed `WritingPipelineInvokers` dataclass with `sflog_invoker` + `prose_invoker` + `parse_prose` callable. |
| `infrastructure/persistence/sqlite/storyos_fact_guard_logs_repository.py` | SQL repo: insert event row, query by `chapter_id`, query by `novel_id` (paginated). |

Plus a DDL migration:
- `infrastructure/persistence/database/migrations/2026_07_07_phase_2b_fact_guard_logs.sql`

### Modified files (4)

| Path | Reason |
|------|--------|
| `application/sf_log/fact_guard_service.py` | Refactor: split single `cpms_invoker` into `sflog_invoker` + `prose_invoker` + `parse_prose`. 3-attempt loop becomes: 1+2 sflog, 3 prose (with regression guard). |
| `engine/pipeline/base.py` | `_hook_step5_post_write_gate` (line 1398-1401): replace stub lambda with real wiring from `fact_guard_cpms.build_writing_pipeline_invokers`. Add `storyos_fact_guard_logs` insert path. Plumb `rewritten_chapter_text` through to Step 6. |
| `domain/novel/entities/chapter.py` | No content change. Verify `set_warnings()` already supports the list-of-dict shape from 2A (it does). |
| `interfaces/api/v1/core/chapters.py` | Append new endpoint `GET /{novel_id}/chapters/{chapter_number}/fact-guard-history`. |

### Tests (5 new + 1 regression fixture)

| Path | Coverage |
|------|----------|
| `tests/unit/sf_log/test_fact_guard_service_prose_path.py` | 3-attempt loop semantics: sflog × 2 → prose × 1; rollback on regression; force_pass on persistent hard. |
| `tests/unit/infrastructure/ai/test_sf_log_prose_rewrite_cpms_node.py` | New node package.yaml + user.md load correctly. Variable schema enforces required fields. |
| `tests/unit/application/sf_log/test_fact_guard_cpms_wiring.py` | `build_writing_pipeline_invokers` returns callables that route to the right CPMS nodes. |
| `tests/unit/sf_log/test_fact_guard_audit_repository.py` | Insert / list_for_chapter / list_for_novel; malformed row rejection; tx safety. |
| `tests/unit/domain/test_prose_rewrite_value_objects.py` | `ProseRewriteResult`, `SFLogRewriteResult` frozen dataclass + type coercion. |
| `tests/integration/sf_log/test_prose_rewrite_regression_e2e.py` | Full-chapter run with mock LLM (provider-level stub): assert rollback path triggers correctly + audit row inserted. |
| `tests/integration/api/test_chapter_fact_guard_history_endpoint.py` | Endpoint returns paginated rows; auth + 404 paths. |
| `tests/regression/fixtures/fact_guard_5ch_prose.json` + `tests/regression/test_phase_2b_prose_rewrite_pass_rate.py` | 5-chapter corpus exercising all 3 modes (auto-pass / sflog-rewritten / prose-rewritten). |

### `sf-log-prose-rewrite/user.md` outline

Distinct from the existing node — same envelope but a different persona:

```
你是一个 prose 对齐助手。给定章节文本、SF_LOG 注释块清单、fact_guard 命中列表：

**硬约束**:
- 只允许改写章节 prose body 中**包含或紧邻** `matched_text` 的句子。
- 段落级放大允许：当问题句子与上下文耦合（例如"他离开了北京，然后到了上海"中"到了上海"必需改）时，可以在最小行内延续里下扩展为同段落重写。
- 严禁：添加新人物 / 改人物身份 / 改叙事者 / 添加原 SF_LOG 未提及的事件。
- 当 prose 修改后仍无法消除全部 HARD 命中，请保留修改、增加可读性优先、并在修改说明中列出剩余 HARD。
- 严禁注释块：不要在你的回复里插入任何 `<!-- SF_LOG ... -->` 注释；SF_LOG 由调用方另行同步。

**输出**: 修改后的章节正文 + 修改说明（diff 摘要列表）。

命中：{{hits}}
SF_LOG 记录：{{sflog_records}}
attempt：第 {{attempt}} 次（共 3 次；prose-mode 仅 1 次）
原始正文：
```
{{chapter_text}}
```

如果你判断 prose 与 SF_LOG 矛盾**过于严重**（例如主情节反转、关键时间线矛盾、人物根本不同）以致无法用段落级重写对齐，请返回原文不变并在修改说明里写 "REQUIRES_PROSE_ROLLBACK"，fact_guard 会回滚并强制 pass。
```

The `REQUIRES_PROSE_ROLLBACK` signal mirrors the existing `REQUIRES_PROSE_REWRITE` semantic in Phase 2A — it lets the LLM opt out of an attempt that's beyond paragraph-level repair.

### `sf-log-prose-rewrite/package.yaml` outline

```yaml
name: SF_LOG prose alignment rewrite
category: rewrite
source: application/sf_log/fact_guard_service.py::FactGuardService::_prose_attempt
description: 'Paragraph-level prose rewrite to align chapter text with SF_LOG records; broader scope than sf-log-rewrite-with-hints'
builtin: true
tags:
- sf_log
- rewrite
- prose
- fact_guard
- phase_2b
output_format: text
variables:
- { name: chapter_text, type: string, required: true, desc: '章节正文（含 SF_LOG 注释）' }
- { name: hits, type: string, required: true, desc: 'fact_guard HARD 命中列表' }
- { name: sflog_records, type: string, required: true, desc: '当前 SF_LOG 记录 JSON' }
- { name: attempt, type: integer, required: true, desc: 'attempt 编号（Phase 2B 中固定为 3）' }
id: sf-log-prose-rewrite
sort_order: 116
```

### Token cap config

Each invoker caps `chapter_text` at a configurable ceiling (default 6000 chars ≈ 1500 tokens). Configurable via `fact_guard_cpms.yaml` with `max_chapter_text_chars: 6000` default. If the chapter exceeds the cap, slice from the conflict centroid.

---

## 3. FactGuardService refactor

### API

```python
@dataclass(frozen=True)
class SFLogRewriteResult:
    mode: Literal["sflog"]
    records: List[SFLogRecord]

@dataclass(frozen=True)
class ProseRewriteResult:
    new_chapter_text: str
    new_records: List[SFLogRecord]       # parsed from new_chapter_text
    rollback_signal: bool = False        # LLM-emitted "REQUIRES_PROSE_ROLLBACK"

SFLogRewriteFn = Callable[
    [List[SFLogRecord], List[GuardHit], int],
    Optional[SFLogRewriteResult],   # None = rewrite unavailable → continue loop unchanged
]
ProseRewriteFn = Callable[
    [str, List[SFLogRecord], List[GuardHit], int],
    ProseRewriteResult,             # always returns; rollback_signal True = discard
]
ParseFn = Callable[[str, int], List[SFLogRecord]]  # (chapter_text, chapter_number) → records

@dataclass(frozen=True)
class FactGuardService:
    """Phase 2B: 3-attempt loop with sflog × 2 + prose × 1 + regression guard.

    audit_repo: optional. When set, every iteration writes a row so writers
    can review the LLM's history in Phase 2C UI.
    """
    engine: RegexEngine
    sflog_invoker: SFLogRewriteFn
    prose_invoker: ProseRewriteFn
    parse_prose: ParseFn
    audit_repo: Optional["FactGuardAuditRepository"] = None
```

Two callables (not one tagged union) because the return shape differs:
- `sflog_invoker` returns `Optional[SFLogRewriteResult]` — `None` means "CPMS unavailable; keep current records".
- `prose_invoker` always returns `ProseRewriteResult`; `rollback_signal=True` means "discard and force_pass".

### `evaluate()` body (pseudocode)

```python
def evaluate(
    self,
    chapter_text: str,
    sflog_records: List[SFLogRecord],
    bible_snapshot: ChapterBibleContext,
    *,
    novel_id: str,
    chapter_id: int,
) -> Tuple[GuardReport, Optional[str]]:
    """3-attempt loop. Returns (GuardReport, rewritten_chapter_text or None)."""
    original_chapter_text = chapter_text
    final_hits: List[GuardHit] = []
    current_records = sflog_records
    hard_before: List[GuardHit] = []
    chapter_number = bible_snapshot.chapter_id   # §8 trap: this is the NUMBER, not DB rowid

    # ── Attempts 1, 2: SF_LOG-mode ───────────────────────────────
    for attempt in (1, 2):
        hits = self.engine.evaluate_chapter(current_records, chapter_text, bible_snapshot)
        final_hits = hits
        hard = [h for h in hits if h.severity is Severity.HARD]

        if not hard:
            self._log(novel_id=novel_id, chapter_id=chapter_id, chapter_number=chapter_number,
                      action="passed", mode="sflog", attempt=attempt,
                      hard_before=len(hard_before), hard_after=0)
            return GuardReport(passed=True, forced_pass=False, attempt=attempt, hits=hits), None

        if attempt < 2:
            rewritten = self.sflog_invoker(current_records, hard, attempt)
            if rewritten is not None:
                self._log(novel_id=novel_id, chapter_id=chapter_id, chapter_number=chapter_number,
                          action="rewritten_sflog", mode="sflog", attempt=attempt,
                          hard_before=len(hard_before), hard_after=len(hard))
                current_records = rewritten.records
            else:
                self._log(novel_id=novel_id, chapter_id=chapter_id, chapter_number=chapter_number,
                          action="no_rewrite_sflog", mode="sflog", attempt=attempt,
                          hard_before=len(hard_before), hard_after=len(hard))
            # continue loop with possibly-updated records

    # ── Attempt 3: Prose-mode with regression guard ──────────────
    hard_before = [h for h in final_hits if h.severity is Severity.HARD]
    if not hard_before:
        # No HARD at attempt 3 even though we entered the prose branch —
        # shouldn't happen given the loop above, but defend anyway.
        return GuardReport(passed=True, forced_pass=False, attempt=2, hits=final_hits), None

    prose_result = self.prose_invoker(
        chapter_text, current_records, hard_before, 3,
    )

    if prose_result.rollback_signal:
        self._log(novel_id=novel_id, chapter_id=chapter_id, chapter_number=chapter_number,
                  action="forced_pass_rollback_llm", mode="prose", attempt=3,
                  hard_before=len(hard_before), hard_after=len(hard_before),
                  notes="llm_signal_REQUIRES_PROSE_ROLLBACK")
        return GuardReport(passed=True, forced_pass=True, attempt=3, hits=final_hits,
                           notes="prose_rollback"), None

    # Re-parse new text, re-evaluate
    new_records = self.parse_prose(prose_result.new_chapter_text, chapter_number)
    new_hits = self.engine.evaluate_chapter(new_records,
                                             prose_result.new_chapter_text,
                                             bible_snapshot)
    new_hard = [h for h in new_hits if h.severity is Severity.HARD]

    if len(new_hard) <= len(hard_before):
        # Accept: keep rewrite (better or equal on hard-hit count)
        self._log(novel_id=novel_id, chapter_id=chapter_id, chapter_number=chapter_number,
                  action="rewritten_prose", mode="prose", attempt=3,
                  hard_before=len(hard_before), hard_after=len(new_hard),
                  diff_excerpt=_format_diff_excerpt(original_chapter_text, prose_result.new_chapter_text))
        return GuardReport(passed=True, forced_pass=True, attempt=3, hits=new_hits,
                           notes=f"prose_rewrite hard={len(new_hard)}"), prose_result.new_chapter_text

    # Regression: rollback to original
    self._log(novel_id=novel_id, chapter_id=chapter_id, chapter_number=chapter_number,
              action="rolled_back_regression", mode="prose", attempt=3,
              hard_before=len(hard_before), hard_after=len(new_hard),
              notes="prose_rewrite_increased_hard")
    return GuardReport(passed=True, forced_pass=True, attempt=3, hits=final_hits,
                       notes="prose_rollback_regression"), None
```

`_log()` writes one row to `audit_repo` if present (silent no-op otherwise).

`_format_diff_excerpt(before, after)` slices both sides to 250 chars around the first divergence (Hamming-style midpoint lookup, or simpler: 250 chars from start of each), returns `f"{before_250}<<<>>>{after_250}"`. Total ≤ 503 chars.

`chapter_id` (kwarg) is the SQLite rowid (for foreign key); `chapter_number` (from `bible_snapshot.chapter_id`) is the human-readable chapter number for display. Both go into the audit row.

### Behavior under infrastructure failure

`prose_invoker` may raise (provider timeout, malformed response). The outer try/except in `base.py:1437-1442` already wraps the entire `service.evaluate(...)` call and writes a `fact_guard:` storyos_failed entry — keeping Phase 2A's "fact_guard must not crash pipeline" semantics.

For **partial** failure (CPMS returns malformed JSON), the prose wiring helper in §4 catches the exception and returns a `ProseRewriteResult(rollback_signal=True, new_chapter_text=chapter_text, new_records=current_records)`. So even malformed responses degrade gracefully (no rewrite, treat as LLM opt-out).

---

## 4. CPMS wiring helper (`application/sf_log/fact_guard_cpms.py`)

Single responsibility: assemble invokers that talk to CPMS, do JSON parsing of the LLM response, handle errors, and surface a consistent result type. No business logic — `FactGuardService` owns loop semantics.

### Module structure

```python
"""CPMS wiring for fact_guard — Phase 2B §4.

Builds sflog_invoker and prose_invoker that talk to the existing CPMS nodes
+ a parse_prose wrapper around the existing parser. Exposes a single
`build_writing_pipeline_invokers(provider, parser, audit_repo)` factory that
the pipeline hook can call per chapter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol

from application.ai_invocation.prompt_assembler import CPMSPromptAssembler
from application.sf_log.fact_guard_service import (
    ProseRewriteFn,
    SFLogRewriteFn,
    ParseFn,
    ProseRewriteResult,
    SFLogRewriteResult,
)
# FactGuardAuditRepository lives in infrastructure/persistence/sqlite/
# (defined in §5). Imported lazily inside append() to avoid circular import
# between domain/application layers and infrastructure.
from domain.storyos.value_objects.sf_log import SFLogRecord
from domain.sf_log.guard_report import GuardHit
# ... deferred import for FactGuardAuditRepository at first use site


class LLMProviderProtocol(Protocol):
    def generate(self, prompt_snapshot) -> str: ...


@dataclass(frozen=True)
class WritingPipelineInvokers:
    sflog_invoker: SFLogRewriteFn
    prose_invoker: ProseRewriteFn
    parse_prose: ParseFn


SFLOG_NODE = "sf-log-rewrite-with-hints"
PROSE_NODE = "sf-log-prose-rewrite"


def build_writing_pipeline_invokers(
    *,
    assembler: CPMSPromptAssembler,
    llm_provider: LLMProviderProtocol,
    parser_service,
    audit_repo: Optional[FactGuardAuditRepository] = None,
    max_chapter_text_chars: int = 6000,
) -> WritingPipelineInvokers:
    """Wire up the two CPMS invokers + parser. Pure factory."""

    def sflog_invoker(
        records: list, hits: list, attempt: int,
    ) -> Optional[SFLogRewriteResult]:
        # 1. render CPMS user.md with hits + records + chapter_text + attempt
        # 2. llm_provider.generate(prompt_snapshot) → raw text response
        # 3. parse JSON for "records": [...]
        # 4. return SFLogRewriteResult(records=new_records)
        #    OR None on parse failure → service treats as CPMS unavailable
        ...

    def prose_invoker(
        chapter_text: str, records: list, hits: list, attempt: int,
    ) -> ProseRewriteResult:
        # 1. render CPMS user.md with hits + records + chapter_text + attempt
        # 2. llm_provider.generate(prompt_snapshot) → raw text response
        # 3. parse JSON for { "chapter_text": "...", "notes": "...",
        #                     "rollback_signal": bool }
        # 4. return ProseRewriteResult(...)
        # - on parse/timeout failure: log + return rollback_signal=True
        #   with original chapter_text + current_records (graceful degradation)
        ...

    def parse_prose(chapter_text: str, chapter_number: int) -> list:
        return list(parser_service.parse(chapter_text, chapter_number))

    return WritingPipelineInvokers(
        sflog_invoker=sflog_invoker,
        prose_invoker=prose_invoker,
        parse_prose=parse_prose,
    )
```

### Error-handling matrix

| Failure | Detection | Handler | Pipeline effect |
|---------|-----------|---------|-----------------|
| Provider timeout / 5xx | `llm_provider.generate` raises | catch, write audit row `provider_failed`, return `None` for sflog; for prose, return `ProseRewriteResult(rollback_signal=True, new_chapter_text=chapter_text, new_records=current_records)` | `force_pass` at attempt 3 if hard persists |
| Malformed JSON response | `json.loads(...)` raises | same as above | same |
| CPMS node missing | `assembler.compile(...)` raises `PromptAssemblyError` | raise out to outer try/except in `base.py:1437` | `ctx.storyos_failed.append("fact_guard: missing CPMS node")`, force_pass |
| LLM returns empty text | `response.strip() == ""` | treat as "no rewrite" (sflog) / "rollback" (prose) | same |
| LLM rolls back voluntarily | response contains `"rollback_signal": true` | respect | rollback, force_pass |

---

## 5. `storyos_fact_guard_logs` table + repository

Single source of truth for fact_guard history. Per-step writes (sflog_attempt, prose_attempt, rollback, force_pass) all land here so a Phase 2C UI can review what each chapter's LLM did.

### DDL (SQLite migration)

```sql
-- File: infrastructure/persistence/database/migrations/2026_07_07_phase_2b_fact_guard_logs.sql

CREATE TABLE IF NOT EXISTS storyos_fact_guard_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id        INTEGER NOT NULL,
    chapter_number    INTEGER NOT NULL,
    novel_id          TEXT NOT NULL,
    attempt           INTEGER NOT NULL CHECK (attempt BETWEEN 1 AND 3),
    mode              TEXT NOT NULL CHECK (mode IN ('sflog', 'prose')),
    action            TEXT NOT NULL CHECK (action IN (
        'passed',                   -- attempts cleared all HARD
        'rewritten_sflog',          -- sflog LLM returned new records
        'no_rewrite_sflog',         -- sflog LLM returned None
        'rewritten_prose',          -- prose LLM succeeded AND kept (regression OK)
        'forced_pass_rollback_llm', -- LLM signaled REQUIRES_PROSE_ROLLBACK
        'rolled_back_regression',   -- prose rewrite increased HARD → original kept
        'provider_failed',          -- exception in CPMS invoke
        'node_missing'              -- CPMS node not published
    )),
    hard_before       INTEGER NOT NULL DEFAULT 0,
    hard_after        INTEGER NOT NULL DEFAULT 0,
    rule_id           TEXT,
    severity          TEXT,
    diff_excerpt      TEXT,                        -- up to 500 chars (before/after glued by "<<<>>>")
    notes             TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (chapter_id)  REFERENCES chapters(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_fact_guard_logs_novel_created
    ON storyos_fact_guard_logs (novel_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fact_guard_logs_chapter
    ON storyos_fact_guard_logs (chapter_id, attempt);
```

### Repository

`infrastructure/persistence/sqlite/storyos_fact_guard_logs_repository.py`:

```python
"""SQLite repository for storyos_fact_guard_logs — Phase 2B §5."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from infrastructure.persistence.database.connection import DatabaseConnection


@dataclass(frozen=True)
class FactGuardLogRow:
    chapter_id: int
    chapter_number: int
    novel_id: str
    attempt: int
    mode: str                          # 'sflog' | 'prose'
    action: str
    hard_before: int = 0
    hard_after: int = 0
    rule_id: Optional[str] = None
    severity: Optional[str] = None
    diff_excerpt: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class FactGuardLogPage:
    rows: List[dict] = field(default_factory=list)
    total: int = 0


class FactGuardAuditRepository:
    """Append-only writes + read queries."""

    def __init__(self, db_path: str) -> None:
        self._db = DatabaseConnection(db_path)

    def append(self, row: FactGuardLogRow) -> int:
        try:
            with self._db.connection() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO storyos_fact_guard_logs
                      (chapter_id, chapter_number, novel_id, attempt, mode,
                       action, hard_before, hard_after,
                       rule_id, severity, diff_excerpt, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row.chapter_id,
                        row.chapter_number,
                        row.novel_id,
                        row.attempt,
                        row.mode,
                        row.action,
                        row.hard_before,
                        row.hard_after,
                        row.rule_id,
                        row.severity,
                        row.diff_excerpt,
                        row.notes,
                    ),
                )
                conn.commit()
                return cur.lastrowid or 0
        except Exception:                       # noqa: BLE001
            return 0

    def append_many(self, rows: Iterable[FactGuardLogRow]) -> List[int]:
        return [self.append(r) for r in rows]

    def list_for_chapter(
        self, chapter_id: int, *, limit: int = 50,
    ) -> FactGuardLogPage:
        ...

    def list_for_novel(
        self, novel_id: str, *, limit: int = 50, offset: int = 0,
    ) -> FactGuardLogPage:
        ...

    def list_for_novels_recent(
        self, novel_id: str, since_iso: str, *,
    ) -> List[FactGuardLogRow]:
        ...
```

### Backward compatibility with Phase 2A in-memory `chapter.warnings`

`chapter.warnings` stays in-memory (2A's contract). Writers reading the existing `GET /chapters/{id}/warnings` endpoint get the *summary* (rule_id + severity + message). The new `GET /chapters/{id}/fact-guard-history` endpoint gives the *full audit*. Two endpoints, two responsibilities.

---

## 6. Step 5 hook changes + base.py integration

The hook at `engine/pipeline/base.py:1359-1453` is the only consumer of `FactGuardService`. Phase 2B replaces the stub lambdas (`base.py:1398-1401`) with real wiring driven by the helper from §4.

### New endpoints

```python
# interfaces/api/v1/core/chapters.py — append

@router.get(
    "/{novel_id}/chapters/{chapter_number}/fact-guard-history",
    response_model=List[FactGuardLogDTO],
)
async def get_chapter_fact_guard_history(
    novel_id: str,
    chapter_number: int,
    repo: FactGuardAuditRepository = Depends(get_fact_guard_audit_repo),
) -> List[FactGuardLogDTO]:
    """Audit trail of every fact_guard attempt (sflog × 2 + prose × 1)."""
    chapter_id = _resolve_chapter_id(novel_id, chapter_number)
    if chapter_id is None:
        raise HTTPException(status_code=404, detail="chapter not found")
    page = repo.list_for_chapter(chapter_id)
    return [FactGuardLogDTO.from_row(r) for r in page.rows]
```

### `_resolve_chapter_id(novel_id, chapter_number) → Optional[int]`

Simple synchronous lookup; no caching in Phase 2B (Q3 defers caching to 2C):

```python
def _resolve_chapter_id(novel_id: str, chapter_number: int) -> Optional[int]:
    """Return the SQLite rowid of `chapters` matching (novel_id, chapter_number).

    None if no such chapter exists.
    """
    with sqlite3.connect(get_db_path()) as conn:
        cur = conn.execute(
            "SELECT id FROM chapters WHERE novel_id = ? AND chapter_number = ? LIMIT 1",
            (novel_id, chapter_number),
        )
        row = cur.fetchone()
        return row[0] if row else None
```

Lives in `interfaces/api/v1/core/chapters.py` alongside `_resolve_chapter_id`'s existing sibling helpers; if the codebase already has a chapter_id lookup pattern, use that instead.

### Plumbing rewritten prose through Step 6

`_hook_step5_post_write_gate` calls `svc.evaluate(...)` which returns `Tuple[GuardReport, Optional[str]]`. The hook unwraps and threads `rewritten_chapter_text` into the return dict:

```python
report, rewritten_text = svc.evaluate(text, records, bible_snapshot, novel_id=..., chapter_id=...)

return {
    "format_errors": format_errors,
    "records": records,
    "match_report": match_report,
    "fact_guard_report": report,
    "rewritten_chapter_text": rewritten_text if rewritten_text is not None else text,
}
```

The Step 5 caller (`BaseStoryPipeline._run_step5_post_write_gate`) reads `rewritten_chapter_text` and feeds it into the save path. If `rewritten_chapter_text == text`, the save is a no-op. Otherwise, the rewritten version is saved.

### Three new helpers on `BaseStoryPipeline` (1-3 lines each)

```python
def _get_llm_provider(self, ctx):
    return (
        getattr(ctx, "llm_provider", None)
        or getattr(self._app_state, "llm_provider", None)
        or _default_fact_guard_provider()
    )

def _get_fact_guard_audit_repo(self, ctx):
    """Default to a no-op repository if app_state doesn't wire one (test/dev)."""
    return getattr(self._app_state, "fact_guard_audit_repo", NOOP_AUDIT_REPO)

def _get_fact_guard_text_cap(self, ctx) -> int:
    return getattr(self._app_state, "fact_guard_text_cap_chars", 6000)
```

`NOOP_AUDIT_REPO` is a module-level singleton: a `FactGuardAuditRepository`-shaped no-op whose `append` is `lambda row: 0`. Defined in `application/sf_log/fact_guard_cpms.py` as a fallback, never raised to logger-spam level.

App-state registration in `interfaces/main.py`:

```python
app_state.fact_guard_audit_repo = FactGuardAuditRepository(db_path)
```

### Per-call vs per-pipeline lifecycle

`build_writing_pipeline_invokers()` is **cheap** to call (constructs 3 closures; no I/O). Called inside the hook, not at module load — lets each invocation use the current `ctx.novel_id` for audit rows. The audit repo is created **once per process**.

---

## 7. Testing strategy

Tests are written before implementation (TDD per the writing-plans skill).

### Unit tests (5 new files, 28+ test cases)

| Test file | Coverage |
|-----------|----------|
| `tests/unit/sf_log/test_fact_guard_service_prose_path.py` | 10 test cases covering every branch of the new 3-attempt loop |
| `tests/unit/infrastructure/ai/test_sf_log_prose_rewrite_cpms_node.py` | New CPMS node package.yaml + user.md load correctly |
| `tests/unit/application/sf_log/test_fact_guard_cpms_wiring.py` | sflog path hits `sf-log-rewrite-with-hints`, prose path hits `sf-log-prose-rewrite` |
| `tests/unit/sf_log/test_fact_guard_audit_repository.py` | Insert / list_for_chapter / list_for_novel; malformed row rejection; tx safety |
| `tests/unit/domain/test_prose_rewrite_value_objects.py` | `ProseRewriteResult`, `SFLogRewriteResult` frozen dataclass + type coercion |

**Test cases for `test_fact_guard_service_prose_path.py`**:

```
1. test_sflog_attempt_clears_hard
2. test_prose_attempt_after_two_sflog_failures
3. test_prose_rewrite_kept_when_hard_count_does_not_increase
4. test_prose_rewrite_rolled_back_on_regression
5. test_prose_rollback_signal_honored
6. test_sflog_invoker_returning_none_treated_as_no_rewrite
7. test_prose_invoker_exception_path
8. test_full_pass_first_attempt_skips_prose
9. test_audit_repo_writes_for_every_attempt
10. test_diff_excerpt_format
```

### Integration tests (2 new files)

| Test file | Coverage |
|-----------|----------|
| `tests/integration/sf_log/test_prose_rewrite_regression_e2e.py` | Full-chapter run with mock LLM → assert rollback path triggers + audit row inserted |
| `tests/integration/api/test_chapter_fact_guard_history_endpoint.py` | Endpoint returns paginated rows; auth + 404 paths |

### Regression (1 file + 1 fixture)

5 chapters exercising all 3 modes (auto-pass / sflog-rewritten / prose-rewritten); pass rate target ≥ 80%.

### Performance (1 file)

`tests/performance/test_prose_rewrite_latency.py`; `@pytest.mark.slow`; P95 < 150ms per chapter (mock LLM, no real provider).

### Acceptance criteria for Phase 2B (gate test)

Mirroring Phase 2A's `scripts/check_phase_2a_metrics.py`, a `scripts/check_phase_2b_metrics.py` gate verifies:

| Metric | Target |
|--------|--------|
| Unit tests pass | 100% (added 28 prose-path tests) |
| Phase 2A tests still pass | 100% |
| Regression corpus pass rate | ≥ 80% |
| Audit row count per chapter | ≥ 1 (action ∈ {`passed`, `rewritten_sflog`, `no_rewrite_sflog`, `rewritten_prose`, `forced_pass_rollback_llm`, `rolled_back_regression`, `provider_failed`, `node_missing`}) |
| `storyos_fact_guard_logs` table created post-migration | yes |
| Python 3.9 compat | preserved |

---

## 8. Risks & open questions

### Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| R1 | **Provider cost overrun** — 3 LLM calls/chapter worst case ×25 chapters/novel = 75 calls/novel. | Med | High | `max_chapter_text_chars: 6000` cap; budget = 3 attempts total; cheaper model selectable via `_get_llm_provider`. |
| R2 | **Voice drift** — paragraph-level rewrite can flatten writer's voice. | High | Med | Prompt instructs minimal narrative disruption; rollback-on-regression guards hard-hit regression; diff surfaces to Phase 2C UI. |
| R3 | **Regression-in-noise** — re-evaluating after rewrite could pass on a new false-negative. | Med | High | `new_hard <= old_hard` is the only keep condition. Audit rows record hard_before/hard_after for empirical study. |
| R4 | **Migration rollout regression** — new SQL table + new helper module = bigger diff than 2A. | Med | Med | TDD-first; pre-merge baseline 1948+; CI runs full suite; rollback = `--no-ff` revert of merge commit. |
| R5 | **CPMS node publishing race** — first production run could see `node_missing` for `sf-log-prose-rewrite`. | Low | High | `assembler.compile()` raises `PromptAssemblyError`; outer try/except catches; audit row `node_missing`; pipeline continues with `force_pass`. |
| R6 | **`base.py` scope creep** — hook block grows from ~60 to ~110 lines. | Med | Low | All wiring lives in `fact_guard_cpms.py`; net `base.py` growth is ~50 lines. |
| R7 | **`eval()` no longer a method** — Python 3.9 frozen-dataclass + method binding still works. | Low | Low | Trivial; covered by `test_fact_guard_service_prose_path`. |

### Open questions (intentional, non-blocking)

| # | Question | Why open | Where to revisit |
|---|----------|---------|------------------|
| Q1 | ~~Should `fact_guard_audit_repo` route through `WriteDispatch`?~~ **RESOLVED: yes.** See decision D1 below. | — | — |
| Q2 | Same DB as `data/plotpilot.db` or separate `data/fact_guard.db`? | Spec assumes same DB for simplicity. | If Phase 2C UI requires high-velocity reads, separate may justify migration. |
| Q3 | Does `_resolve_chapter_id(novel_id, chapter_number)` need a memoized cache? | Probably yes at scale. | Phase 2C profile-driven addition. |
| Q4 | Admin endpoint `force_prose_rewrite`? | Useful for debugging. | Add in 2C alongside history UI. |
| Q5 | Strict JSON-schema validation for partial responses? | Spec uses try/except broadly. | Add in 2C. |
| Q6 | Token-level retry of partial LLM responses? | Spec treats as `provider_failed` → rollback. | Configurable per-provider retry policy. |
| Q7 | Bump `diff_excerpt` from 500 to 1000 chars? | Tunable in `fact_guard_cpms.yaml`. | 2C review feedback. |
| Q8 | Will Phase 2A `ctx.metadata["storyos_warnings"]` shape need to change? | Spec assumes no. Backward compatible. | Confirm during 2C review UI integration. |

### Resolved decisions

**D1. Audit writes route through `WriteDispatch`.** `CLAUDE.md` mandates "All SQLite writes go through a single-writer dispatcher (`Write Dispatch`)". Although fact_guard audit is append-only and low-frequency, the rule is a hard project convention.

**Implementation:**

```python
# in infrastructure/persistence/sqlite/storyos_fact_guard_logs_repository.py

from infrastructure.persistence.database.write_dispatch import WriteDispatch

class FactGuardAuditRepository:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def append(self, row: FactGuardLogRow) -> int:
        """Queues the INSERT into WriteDispatch; returns 0 immediately.
        Read the actual rowid by querying the dispatcher after a small
        settle window, or accept "no rowid returned" semantics for audit.

        Audit writes are not on the critical path; failure here is silent
        (no-op equivalent to direct-DB exception swallowing).
        """
        try:
            return WriteDispatch.enqueue_txn_batch(
                self._db_path,
                self._insert_callable,
                (row,),
            ) or 0
        except Exception:                       # noqa: BLE001
            return 0

    @staticmethod
    def _insert_callable(conn, row: FactGuardLogRow) -> int:
        """Runs on the dispatcher thread with a TxnCollectingConnection."""
        cur = conn.execute(
            """
            INSERT INTO storyos_fact_guard_logs
              (chapter_id, chapter_number, novel_id, attempt, mode,
               action, hard_before, hard_after,
               rule_id, severity, diff_excerpt, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.chapter_id, row.chapter_number, row.novel_id,
                row.attempt, row.mode, row.action,
                row.hard_before, row.hard_after,
                row.rule_id, row.severity, row.diff_excerpt, row.notes,
            ),
        )
        return cur.lastrowid or 0
```

`enqueue_txn_batch` returns the lastrowid when the batch flushes; this is non-deterministic from the caller's perspective because the dispatcher batches writes. For audit we accept "0 means queued or failed" — `list_for_chapter` reads what's actually persisted.

Reads (the `GET /chapters/{id}/fact-guard-history` endpoint) use a regular `sqlite3.Connection` read; WriteDispatch is write-only.

---

### YAGNI list

Things that could be in Phase 2B but are intentionally **not**:

- Streaming prose rewrite output
- Multi-provider fallback
- Per-rule custom rewrite prompts
- Inline diff visualization in API response
- Voice fingerprinting

### Done definition (binary gate)

1. **All Phase 2A tests still pass** (1948 unit + 2A integration + regression). Zero regressions.
2. **All new Phase 2B tests pass** (28+ unit + 2+ integration + regression + performance).
3. **Regression corpus** ≥ 80% pass rate.
4. **`storyos_fact_guard_logs` table** exists post-migration with proper indexes.
5. **Audit row count** ≥ 1 per pipeline fact_guard evaluation.
6. **Python 3.9 compat** preserved.
7. **CLAUDE.md** updated with Phase 2B section.
8. **Merge** to `master` + push to `origin`.

---

## Acceptance

User has approved all 8 design sections. Awaiting user review of the written spec before transitioning to the writing-plans skill.
