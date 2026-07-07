# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PlotPilot (墨枢) is an open-source **narrative engine kernel** for long-form AI-assisted fiction writing. It's not a chatbot — it's a systems-engineering approach to maintaining character consistency, causal chain integrity, and foreshadowing closure across hundreds of thousands of words via structured narrative state management.

## Commands

```bash
# Backend — start API server (port 8005)
uvicorn interfaces.main:app --host 127.0.0.1 --port 8005 --reload

# CLI entry point (HTTP server only — daemon is separate, see below)
python cli.py serve --reload

# Engine daemon (production writing pipeline) — single production entry point
python scripts/start_daemon.py
# Toggle to legacy writing path if needed:
#   PLOTPILOT_USE_STORY_PIPELINE=off python scripts/start_daemon.py

# Database migrations (idempotent; tracks applied files in migrations_applied)
python scripts/run_migrations.py

# Frontend — dev server (port 3000, proxies /api → 8005)
# `predev` hook auto-runs scripts/sync-builtin-taxonomy.mjs first
cd frontend && npm run dev

# Frontend — type-check (vue-tsc) + build
cd frontend && npm run build

# Frontend — Tauri desktop client
cd frontend && npm run tauri:dev
cd frontend && npm run tauri:build

# Tests — all
pytest tests/ -v

# Tests — unit / integration / dag / e2e (split by tree)
pytest tests/unit -v
pytest tests/integration -v
pytest tests/dag -v
pytest tests/e2e -v

# Tests — by marker (see pytest.ini: unit, integration, slow, asyncio)
pytest tests/ -m unit -v
pytest tests/ -m integration -v
pytest tests/ -m "not slow" -v

# Single test (file::class::test or by -k substring)
pytest tests/unit/domain/test_chapter.py::TestChapter::test_summary_extraction -v
pytest tests/ -k "tension_score" -v

# Tests with coverage
pytest tests/ --cov=. --cov-report=term-missing

# Install dependencies
pip install -r requirements.txt           # core (lightweight)
pip install -r requirements-local.txt     # + local embedding models
```

## Architecture

PlotPilot is **DDD four layers + a separate engine kernel**. The four DDD layers (`domain/`, `application/`, `infrastructure/`, `interfaces/`) hold the stable business model and its HTTP/external surface; the top-level `engine/` package is an *independent runtime kernel* — the production writing pipeline — kept decoupled so that ecosystem extensions (vertical tools, editor plugins, custom pipelines) plug in without polluting the domain core. Detailed diagram in `docs/ARCHITECTURE.md`.

```
domain/           # Domain layer — zero external deps, pure business logic
  novel/          # Novel aggregate, Chapter entity, Storyline, Foreshadowing registry
  bible/          # Story Bible aggregate root (composes cast/worldbuilding/structure)
  cast/           # Character roster (ensemble-level view, distinct from per-character model)
  character/      # Character entity model (POV firewall, frequency scheduling)
  worldbuilding/  # World setting triples, locations, factions
  structure/      # Macro structure (part/volume/act/chapter scaffolding)
  knowledge/      # Knowledge triples, story knowledge graph
  evolution/      # State change events — character status, item transfer, fact reveal
  memory/         # Per-character compiled context, arc projection
  prop/           # Props / items tracked across chapters
  engine/         # Engine-side domain types shared across application engines
  ai/             # LLM service interfaces, prompt value objects, token stats
  shared/         # Shared kernel (base classes, domain events, exceptions)

application/      # Application layer — use-case orchestration
  engine/         # AI generation service, autopilot daemon, DAG executor, context assembler
  blueprint/      # Macro planning (part-volume-act), act-level beat sheets
  world/          # Bible management, knowledge graph construction
  audit/          # Chapter review, macro restructuring, cliché scanner
  analyst/        # Style analysis, tension analysis, drift detection
  workflows/      # Post-chapter pipeline orchestration (auto-generation, beat extraction)
  novel/          # Novel/chapter CRUD services
  onboarding/     # New-book wizard and prerequisite setup
  narrative_engine/  # Story pipeline (10-step BaseStoryPipeline) + BFF read surface
  narrative/      # Narrative-domain application services (shared by engines)
  manuscript/     # Manuscript-level read/write operations (chapter body, revisions)
  evolution/      # Evolution Engine — state-change tracking & gate validation
  governance/     # Governance Engine — narrative-contract enforcement
  memory/         # Memory Engine — character-context compilation
  codex/          # Chronicles (Codex) — dual-helix plot timeline + semantic snapshots
  snapshot/       # Snapshot manager (checkpoint create / rollback / HEAD)
  checkpoint/     # Checkpoint persistence primitives
  character/      # Character-level use cases
  prop/           # Prop/item use cases
  reader/         # Reader-facing read models
  workbench/      # Workbench-specific aggregation (frontend BFF helpers)
  ai/             # AI orchestration helpers (prompt assembly, retries)
  ai_invocation/  # AI call logging and review
  core/           # Cross-cutting application primitives
  services/       # Misc application services
  dtos/           # Cross-layer DTOs

engine/           # Engine kernel — independent production runtime (NOT inside application/)
  runtime/        # EngineDaemon, StoryPipelineRunner, writing/audit/macro delegates, quality guardrails
  pipeline/       # BaseStoryPipeline — 10-step chapter generation pipeline (steps, beat contracts, prose composer, recovery)
  pipelines/      # Themed pipeline registry & extensions (wuxia, generic) → registered via example adapters
  core/           # Engine-side entities, ports, services, value objects (hexagonal ports for the runtime)
  infrastructure/ # Engine-internal events, memory orchestration, checkpoint adapters
  application/    # Engine-side use cases: writing orchestrator, plot state machine, quality guardrails
  examples/       # Reference themed pipelines (short_drama, wuxia) showing how to register a new genre

infrastructure/   # Infrastructure layer — replaceable tech implementations
  ai/             # LLM clients, ChromaDB/Qdrant vector store, embedding services
    providers/    # anthropic_provider, openai_provider, gemini_provider, mock_provider
    prompt_packages/  # YAML-overridable prompt packs (20+ injection points)
    prompts/      # Raw prompt templates
  persistence/    # SQLite repositories, Write Dispatch (single-writer router), mappers
  json_stream/    # Streaming JSON parsing utilities
  export/         # DOCX / EPUB / PDF export
  runtime/        # Data directory, log environment, process-level runtime config
  engine/         # Engine-side infra adapters

interfaces/       # Interface layer — external boundaries
  main.py         # FastAPI app entrypoint
  daemon_manager.py   # Backend-side auto-pilot process manager
  runtime.py      # Runtime state container (DI wiring)
  api/v1/         # Versioned REST API (FastAPI), split by subdomain:
    core/ engine/ world/ blueprint/ audit/ analyst/ prop/ reader/ workbench/ meta/
    anti_ai.py    # Anti-AI-detection endpoints
    system.py     # System / health endpoints

shared/           # Cross-end taxonomy & classification resources (not part of DDD layers)
config/           # Runtime YAML — generation_profiles, policy_packs, performance, genre_packs
scripts/          # Operational scripts (start_daemon, run_migrations, evaluation)
docs/             # ARCHITECTURE.md, BUILD_INSTALLER.md, embedding download guide, screenshots
```

### Five-subsystem mental model

When reasoning about runtime behavior, think in terms of five cooperating subsystems rather than folder names:

1. **Narrative State Machine** — Story Bible, chapter-summary chain, event stream, storyline DAG, foreshadowing registry. The persistent "memory" fed into each generation.
2. **Vector Retrieval Layer** — Two parallel indexes: chapter content (ChromaDB / Qdrant) and `(subject, relation, object)` knowledge triples (structured + semantic hybrid).
3. **Engine Runtime** — `engine/runtime/engine_daemon.py` → `EngineDaemon` → `StoryPipelineRunner`, driving the 10-step `BaseStoryPipeline`. Single production entry: `scripts/start_daemon.py`.
4. **Prompt Strategy Layer** — 20+ independent injection points; each is YAML-overridable via `infrastructure/ai/prompt_packages/`. Switch task type (短篇 / 长篇 / 游戏剧本) by switching prompt-pack dirs, no code change.
5. **Quality Monitor** — Per-chapter tension score (0–10), style-similarity drift, cliché scanner; drift triggers *targeted rewrite* rather than rollback.

### Two entry points to know

- **`python cli.py serve --reload`** → FastAPI HTTP server only. The engine daemon is started *separately* (auto-launched by FastAPI unless `DISABLE_AUTO_DAEMON=1`).
- **`python scripts/start_daemon.py`** → builds the dependency graph and starts `EngineDaemon` directly. Use this when iterating on the runtime itself, running headless generation, or isolating daemon behavior from the API.

To temporarily disable the default `StoryPipeline` writing path (e.g., fall back to legacy chapter writing): `PLOTPILOT_USE_STORY_PIPELINE=off`.

## Engine Subsystems

PlotPilot contains multiple specialized engines, each with a distinct role in the narrative production pipeline:

| Engine | Layer | Role |
|--------|-------|------|
| **Autopilot Daemon** | `application/engine/services/` | Staged state machine driving full-novel generation: macro planning → act beats → chapter loop → post-chapter pipeline. Circuit breaker, SSE streaming, checkpoint snapshots. |
| **DAG Engine** | `application/engine/dag/` | LangGraph-based DAG executor with topological parallel execution. Compiles `DAGDefinition` → `StateGraph`, supports checkpoint/resume. Nodes split by concern: planning, context, execution, review, validation, gateway, anti-AI, props, world. |
| **Narrative Engine** | `application/narrative_engine/` | Novelist-facing **BFF read surface**. Aggregates read models across all domains via `NarrativeLens` dimensions (manuscript, macrocosm, plot structure, time/revision, subtext, persona/voice, craft/quality, knowledge graph, automation, platform). Exposed via `/api/v1/narrative-engine/`. |
| **Evolution Engine** | `application/evolution/` + `domain/evolution/` | Tracks story-world state changes across chapters: character status (alive/dead/missing), item transfers, fact reveals, storyline progress, emotional residue. Gate validation ensures state transitions are narratively coherent. |
| **Governance Engine** | `application/governance/` | Enforces narrative contracts: canonical storylines with alias merging, forbidden early payoffs, reveal budgets, theme anchors. Produces `GovernanceReport` with severity-ranked issues. |
| **Memory Engine** | `application/memory/` + `domain/memory/` | Compiles character-specific context across chapters, projects character arcs forward, imports legacy memory formats. |
| **Chronicles (Codex)** | `application/codex/` | Dual-helix chronicles: zipper-merges plot timeline with semantic snapshots by chapter index for time/revision queries. |
| **Snapshot Manager** | `application/snapshot/` | Checkpoint creation, rollback, and HEAD tracking for the autopilot state machine. |

## Key Design Decisions

- **All SQLite writes** go through a single-writer dispatcher (`Write Dispatch`) to eliminate concurrent write conflicts
- **LLM providers** are abstracted behind a unified interface; switching models doesn't touch business code. Providers: Anthropic, OpenAI-compatible, Ark (Doubao), Gemini
- **Prompt strategy**: 20+ independent prompt injection points, each overridable via YAML config in `infrastructure/ai/prompt_packages/`
- **Vector retrieval**: Two parallel indexes — chapter content (ChromaDB / Qdrant) and knowledge triples (structured + semantic hybrid query)
- **Autopilot daemon** drives full-novel generation as a staged state machine with circuit breaker protection, checkpoint snapshots, and SSE real-time streaming
- **Bible composition**: `domain/bible/` is the aggregate root; `cast/`, `character/`, `worldbuilding/`, `structure/` are sub-aggregates broken out for independent evolution. Don't reach across them — go through the bible aggregate or an application service.
- **Engines vs. application services**: The "Engines" in the table above (Evolution, Governance, Memory, Codex, Snapshot) each have their own `application/<name>/` package with a clear public service; treat them as bounded contexts and avoid cross-importing internals.
- **Frontend** uses `@/` alias for `frontend/src/`; chunk splitting: naive-ui, echarts, vue-runtime, vendor. Vue 3 + TypeScript + Vite + Pinia + Vue Router + Vue Flow (DAG viz) + ECharts. Tauri 2.x for desktop builds.

### StoryOS 工作台（v1.2）

项目接入 StoryForge2 tier_0 机制后，工作台新增 "叙事资产" 入口：
- 路径：`/book/:slug/storyos`
- 8 Registry（冲突/谜题/反转/承诺/揭示/预期/目标/伏笔）CRUD — 40 个端点
- CascadeGraph 可视化
- SFLogInspector 章节 SF_LOG 注释解析
- PredeclaredDiff 预声明 vs 实际产出三色高亮
- Migration 工具（旧 `foreshadowings` 表 → `storyos_foreshadowing_v1`，断点续跑 + 审计 + 回滚）

**当前里程碑状态**（2026-07-07 验收）：
- 1A-1E 全部合并。1E migration 端点已从 501 桩升级为真实 handler（200/404）。
- cascade simulate / replay 仍为 501（设计：1F 真实联级联接；当前通过 SFLogInspector 替代路径）。
- Python 3.9 兼容：8 个 PEP 604 + dataclass kw_only + async_bridge timeout 异常归一化已修。

详细设计见 `docs/superpowers/specs/2026-07-02-storyos-integration-design.md`
实施计划见 `docs/superpowers/plans/2026-07-02-storyos-phase-1d-frontend-api.md` 与 `2026-07-02-storyos-phase-1e-migration.md`
验收清单见 `docs/superpowers/checklists/2026-07-02-storyos-1d-acceptance.md`

### Phase 2A — Tier 0 SF_LOG Fact Guard (v1.3)

项目 v1.2 之后引入 Tier 0 fact_guard：
- 12 YAML 驱动规则覆盖所有 11 类 SFLogType（含 1 类全局唯一性）
- post-write 同步门（嵌在 Step 5 `_hook_step5_post_write_gate` 末尾）
- 3 attempt 重试 + force-pass；3-attempt 后 HARD 命中落 `chapter.warnings`
- 新增 `Chapter.warnings` 字段 + `GET /api/v1/chapters/{id}/warnings` 端点
- 新 CPMS 节点 `sf-log-rewrite-with-hints`（只重写 SF_LOG 块，prose body 不变）

详见 `docs/superpowers/specs/2026-07-07-phase-2a-fact-guard-design.md`
实施计划见 `docs/superpowers/plans/2026-07-07-phase-2a-fact-guard.md`

### Phase 2B — Tier 0 SF_LOG Prose Rewrite (v1.4)

项目 v1.3 之后引入 Tier 0 prose 改写层：
- 3-attempt loop：sflog × 2（已有节点 sf-log-rewrite-with-hints）+ prose × 1（新节点 sf-log-prose-rewrite）+ force_pass
- 自动升级：3 次 SF_LOG-only 仍 HARD → attempt 3 prose
- 段落级重写：prose 模式可改含 `matched_text` 的句子 + 同段落上下文延续
- 单 prose attempt + regression guard：`new_hard < old_hard` 才能落地，否则回滚原文
- 新 CPMS 节点 `sf-log-prose-rewrite`（package.yaml sort_order=116）
- 新增值对象：`ProseRewriteResult`, `SFLogRewriteResult`, `FactGuardLogRow`, `FactGuardAction`, `FactGuardMode`
- 新 SQLite 表 `storyos_fact_guard_logs`（8 种 action enum，写入走 WriteDispatch per D1；读取走直连）
- 新 endpoint `GET /api/v1/novels/{novel_id}/chapters/{chapter_number}/fact-guard-history`
- 新 helper `_resolve_chapter_id(novel_id, chapter_number)`（API 层）+ `_resolve_chapter_rowid(ctx)`（pipeline 层）
- `fact_guard_cpms.py`：CPMS 接线工厂 + `NOOP_AUDIT_REPO` 回退
- 验收门禁：`scripts/check_phase_2b_metrics.py`

详见 `docs/superpowers/specs/2026-07-07-phase-2b-prose-rewrite-design.md`
实施计划见 `docs/superpowers/plans/2026-07-07-phase-2b-prose-rewrite.md`

## Environment Variables

Copy `.env.example` to `.env` and configure at minimum one LLM key (`ANTHROPIC_API_KEY` or `ARK_API_KEY`). Key vars: `EMBEDDING_SERVICE` (openai/local), `VECTOR_STORE_TYPE` (chromadb), `LOG_LEVEL`, `LOG_FILE`, `CORS_ORIGINS`, `DISABLE_AUTO_DAEMON`.

## Data

- SQLite DB: `data/plotpilot.db` (auto-created; falls back from old `aitext.db`)
- Vector store: `data/chromadb/`
- App logs: `logs/plotpilot.log`
- `.env` is gitignored; never commit secrets

## Commit safety boundary (from README)

Do **not** commit any of the following — both for repo hygiene and to avoid leaking private content:

- `.env`, API keys, private endpoints in `.env`
- `data/`, `logs/`, SQLite DB, vector store, runtime caches
- Office documents (`.docx`, `.pptx`, `.xlsx`) — especially unpublished setting drafts, business plans, contracts, customer material
- Build artifacts, installer bundles, Tauri / PyInstaller output

If you need to commit example material, scrub it to desensitized Markdown / JSON / YAML and confirm it contains no real keys, real user data, or unpublished creative content. Logging configuration: see `README_LOGGING.md`.
