# StoryOS tier_0 集成 PlotPilot — 实施计划索引

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 StoryForge2 的 tier_0 SF_LOG 机制（SF_LOG 标签解析 + 8 个叙事资产注册表 + 级联事务管理器）有机融入 PlotPilot 的 10 步 BaseStoryPipeline，建立可观测、可回滚、可审计的 narrative arc 状态管理基础设施。

**Architecture:** 新增 bounded context `storyos/`（与 `evolution/` 平级），通过 `EvolutionBridgeService` 与 Evolution Engine 协同——SF_LOG 提取为 LogRecord 后，**单 SQL 事务**双写 StoryOS + Evolution。Pipeline 钩子分布在 Step 1/3/5/6，触发「预声明 → 插入 → 解析 → 双写」三级流程。Phase 1 不含 CreativeOS。

**Tech Stack:** Python 3.14 + FastAPI 0.109 + Pydantic 2 + SQLAlchemy + SQLite（Write Dispatch 扩展 transaction）+ Vue 3 + Naive UI + Pinia + Vue Flow + ECharts。Prompt 包沿用现有 YAML 注入点机制，新增 `sflog_directive`。

---

## 子计划文件

本计划拆分为 **5 个子阶段 + 1 个索引**。每阶段独立可执行，子阶段完成后可独立验证。

| 阶段 | 文件 | 内容 | LOC | 估时 |
|---|---|---|---|---|
| **1A Foundation** | [`2026-07-02-storyos-phase-1a-foundation.md`](./2026-07-02-storyos-phase-1a-foundation.md) | domain + persistence 11 张表 + WriteDispatch 扩展 + 迁移脚本 | ~3000 | 1 周 |
| **1B Application** | [`2026-07-02-storyos-phase-1b-application.md`](./2026-07-02-storyos-phase-1b-application.md) | parsers + services + bridge + compliance gate | ~2500 | 1.5 周 |
| **1C Engine** | [`2026-07-02-storyos-phase-1c-engine.md`](./2026-07-02-storyos-phase-1c-engine.md) | StoryOSDelegate + 钩子 + ScenePlan 扩展 | ~500 | 3 天 |
| **1D Frontend + API** | [`2026-07-02-storyos-phase-1d-frontend-api.md`](./2026-07-02-storyos-phase-1d-frontend-api.md) | 51 REST 端点 + StoryOSHub + 6 子视图 | ~2000 | 1 周 |
| **1E Migration** | [`2026-07-02-storyos-phase-1e-migration.md`](./2026-07-02-storyos-phase-1e-migration.md) | Foreshadowing 单向迁移 + CLI | ~300 | 2 天 |
| **总计** | — | — | **~8300 LOC + ~3000 测试** | **~5 周** |

---

## 决策记录（Decisions）

9 项 Q&A 决策 + 3 项 review 修订（来自 spec Section 0）：

| # | 议题 | 决策 | 锁定的设计点 |
|---|---|---|---|
| Q1 | 交付节奏 | 分两阶段（Phase 1 = tier_0，Phase 2 = CreativeOS） | 本文仅覆盖 Phase 1；Phase 2 单独 spec |
| Q2 | SF_LOG 与 Evolution 关系 | **互补**：SF_LOG 作源头（LLM 自证清白），Evolution 作门控（合法性校验） | `EvolutionBridgeService` 双写协同 |
| Q3 | Registry 持久化 | SQLite + ORM Mapper | 跨表原子性走 SQL 事务（扩展 WriteDispatch） |
| Q4 | Pipeline 集成时机 | **三层**：预声明（Step 2）+ Writer 插入（Step 4）+ 解析（Step 5-6） | ScenePlan.predeclared_changes 字段 |
| Q5 | Registry 范围 | **全量 8 个**（含 Foreshadowing 迁移） | 旧 `domain_novel.foreshadowings` 单向迁移 |
| Q6 | 前端暴露 | 完整工作台面板（StoryOSHub + 6 子视图） | 新增 `/workbench/:novelId/storyos` 路由 |
| Q7 | LLM Provider 兼容性 | 统一 prompt + 自适应增强 | 通过合规率数据动态调整 directive |
| Q8 | 现有项目迁移 | **惰性初始化 + 旧伏笔自动转换**（单向迁移，旧表只读） | 一次性脚本 + 旧表保留至 Phase 2 |
| Q9 | 架构整合方式 | **新 bounded context `storyos/`**，与 Evolution 平级 | 完整 DDD 四层 |
| R1 | Predeclared asset 形态 | `asset_id \| asset_pair` 二选一 + model_validator | 关系型 SF_LOG（`char_a/char_b`）支持 |
| R2 | conflict_escalate 是否触发级联 | **是**：新增 `CONFLICT_ESCALATED` 触发器，关联 expectation `intensity += 30` | 与 StoryForge2 不同（更激进） |
| R3 | 失败 D 重试策略 | **两级**：predeclared 缺失→retry；额外 SF_LOG→warn（不 retry） | CircuitBreaker 扩展多 gate |

---

## 文件结构总览（按 DDD 层）

每个子计划创建/修改的文件按 DDD 层分组。**详细责任在每个子计划文件 Section 2 / 任务 Files 字段**。

### Domain 层（1A 全部 + 1B 部分）

| 子包 | 关键文件 | 责任 |
|---|---|---|
| `domain/storyos/__init__.py` | 1A Task C8 | 重新导出 8 实体 + contracts |
| `domain/storyos/contracts.py` | 1A A1-A5 | `AssetStatus` / `SFLogType` / `CascadeTrigger` / `FORBIDDEN_TRANSITIONS` / `RegistryAsset` Protocol |
| `domain/storyos/value_objects/sf_log.py` | 1A B1 | `SFLogRecord` + `SFLogParam`（parser 输出格式） |
| `domain/storyos/value_objects/cascade.py` | 1A B2-B3 | `CascadeStep` / `CascadeRules` / `CascadeResult` |
| `domain/storyos/value_objects/predeclared.py` | 1A B4 | `PredeclaredChange` / `PredeclaredChanges` |
| `domain/storyos/value_objects/match_report.py` | 1A B5 | `MatchReport`（spec §4.4 锁定两级重试） |
| `domain/storyos/value_objects/format_error.py` | 1A B5 | `FormatError` |
| `domain/storyos/entities/{8 个}.py` | 1A C1-C8 | 8 个 narrative asset 实体（Conflict/Mystery/Twist/Promise/Reveal/Expectation/Goal/Foreshadowing） |

### Application 层（1B 全部 + 1E 部分）

| 子包 | 关键文件 | 责任 |
|---|---|---|
| `application/storyos/parsers/sf_log_regex_parser.py` | 1B A1 | 11 类 SF_LOG 零 LLM 提取 |
| `application/storyos/parsers/sf_log_format_validator.py` | 1B A2 | 格式严格校验 |
| `application/storyos/parsers/sf_log_action_mapper.py` | 1B A3 | SFLogRecord → EvolutionAction（6 映射 + 5 跳过） |
| `application/storyos/services/registry_service.py` | 1B B1-B4 | 8 个 Registry 业务逻辑（CRUD + 状态转换） |
| `application/storyos/services/cascade_service.py` | 1B C1-C3 | BFS 级联 + 校验 + 原子提交（MAX_CASCADE_DEPTH=3） |
| `application/storyos/services/sf_log_parser_service.py` | 1B F2 | parse → validate → match 编排 |
| `application/storyos/services/evolution_bridge_service.py` | 1B D1-D3 | 单 SQL 事务三操作 + bridge_log 失败聚合 |
| `application/storyos/services/snapshot_projector.py` | 1B F1 | Snapshot 投影 |
| `application/storyos/services/circuit_breaker_integration.py` | 1B E1-E2 | `SFLogComplianceGate` 4 决策 |
| `application/storyos/services/foreshadowing_migration_service.py` | 1B stub → 1E 补完 | 旧伏笔迁移业务逻辑 |
| `application/engine/services/circuit_breaker.py` | 1B E1（修改）| **扩展**为多 gate（向后兼容） |

### Infrastructure 层（1A 全部 + 1E 部分）

| 子包 | 关键文件 | 责任 |
|---|---|---|
| `infrastructure/persistence/database/write_dispatch.py` | 1A D1-D3（修改）| **新增** `transaction()` + `WriteTransaction.queue_apply()`（向后兼容） |
| `infrastructure/persistence/storyos/__init__.py` | 1A D4 | 子包入口 |
| `infrastructure/persistence/storyos/schemas/base.py` | 1A D4 | `BaseRegistrySchema` mixin（11 表共用字段） |
| `infrastructure/persistence/storyos/schemas/{8+3}_schema.py` | 1A E1-E3 | 8 registry + 3 audit/log SQLAlchemy ORM |
| `infrastructure/persistence/storyos/schemas/CONVENTIONS.md` | 1A D5 | Schema 约定文档 |
| `infrastructure/persistence/storyos/mappers/{11}_mapper.py` | 1A E1-E3 | ORM ↔ Domain 双向映射 |
| `infrastructure/persistence/database/migrations/versions/0001_storyos_init.py` | 1A F1 | Alembic 迁移：创建 11 张表 |
| `infrastructure/persistence/storyos/migration_log_schema.py` | 1E 新增 | 迁移断点 + 审计表 |
| `infrastructure/persistence/storyos/migration_log_mapper.py` | 1E 新增 | migration_log mapper |

### Interfaces 层（1D 全部）

| 子包 | 关键文件 | 责任 |
|---|---|---|
| `interfaces/api/v1/storyos/__init__.py` | 1D A3 | 子包入口 |
| `interfaces/api/v1/storyos/schemas/{8}_schemas.py` | 1D A1 | 8 entity × 2 schema = 16 Pydantic DTO |
| `interfaces/api/v1/storyos/routes/{8+4}_routes.py` | 1D B1-C3 | 8 registry × 5 CRUD + cascade/sflog/migration/health |
| `interfaces/api/v1/storyos/crud_factory.py` | 1D A2 | 8 registry 样板生成器 |

### Engine 层（1C 全部）

| 子包 | 关键文件 | 责任 |
|---|---|---|
| `engine/runtime/storyos_delegate.py` | 1C B1-B4 | 唯一引擎接入点（3 方法合一：load_active_assets_for_context / validate_predeclared_changes / apply_post_write_results） |
| `engine/pipeline/beat_contracts.py` | 1C A1-A2 | **扩展** `ScenePlan.predeclared_changes` 字段 |
| `engine/runtime/daemon_host.py` | 1C B4 | DI 注入 StoryOSDelegate |
| `engine/pipeline/story_pipeline_runner.py` | 1C C1-C2 | 4 钩子接入（Step 1/3/5/6） |
| `config/prompt_packages/nodes/chapter-prose-generation/package.yaml` | 1C D1 | 新增 `sflog_directive` 注入点 |

### Frontend 层（1D 全部）

| 子包 | 关键文件 | 责任 |
|---|---|---|
| `frontend/src/views/workbench/storyos/StoryOSHub.vue` | 1D D3 | 主面板（侧边栏 + tab 切换） |
| `frontend/src/views/workbench/storyos/{5} 子视图.vue` | 1D E1-E4 | RegistryList/RegistryDetailDrawer/CascadeGraph/SFLogInspector/PredeclaredDiff |
| `frontend/src/components/workbench/storyos/{4} 组件.vue` | 1D E1-E2 | AssetCard/CascadeStepNode/IntensityChart/StatusBadge |
| `frontend/src/stores/storyos/{3} store.ts` | 1D D1 | queries/cascade/sflog Pinia 模块 |
| `frontend/src/router/workbench.ts` | 1D D2 | `/workbench/:novelId/storyos` 路由 |

### Scripts 层（1A 脚手架 + 1E 完整）

| 文件 | 责任 |
|---|---|
| `scripts/migrate_storyos.py` | 1A F2 脚手架 → 1E 完整（dry-run / execute / rollback 三子命令） |

---

## 跨阶段类型契约（Phase 1 内部接口）

本节列出**跨阶段的关键类型与扩展点**——这些是 1A/1B 产出，1C/1D 必须消费的"接口契约"。任何破坏这些契约的修改视为 Phase 1 内破坏性变更，需要全阶段回归。

### 契约 1：`WriteDispatch` 扩展（1A 产出 → 1B 消费）

**位置**：`infrastructure/persistence/database/write_dispatch.py`

**新增**（向后兼容）：
```python
class WriteDispatch:
    @contextmanager
    def transaction(self) -> Iterator[WriteTransaction]: ...

class WriteTransaction:
    def queue(self, op: Callable[[sqlite3.Connection], None]) -> None: ...  # 旧 API 保留
    def queue_apply(self, fn: Callable[..., None], *args, **kwargs) -> None: ...  # 新 API
```

**消费方**：1B `EvolutionBridgeService.apply_sflog_batch()` 在单事务内 queue_apply 三操作。

**回归测试**：`test_bridge_sql_transaction.py`（spec §5.3 锁定）+ `pytest tests/ -m "not slow"` 全过（向后兼容）。

### 契约 2：`CircuitBreaker` 多 gate 扩展（1B 产出 → 1B 自身消费）

**位置**：`application/engine/services/circuit_breaker.py`

**新增**（向后兼容）：
```python
class CircuitBreaker:
    MAX_RETRIES = 3
    def get_retry_count(self, scope_id: int, gate: str = "default") -> int: ...
    def record_retry(self, scope_id: int, gate: str, hints: str) -> None: ...
    def record_force_pass(self, scope_id: int, gate: str, notes: str) -> None: ...
```

**默认值**：`gate="default"` 保持现有行为，避免破坏现有调用方。

**消费方**：`SFLogComplianceGate` 复用同一 `CircuitBreaker` 实例，独立计数（`gate='sflog_compliance'` vs `gate='fact_guard'`）。

### 契约 3：`ScenePlan.predeclared_changes` 字段（1C 产出 → 1D 消费）

**位置**：`engine/pipeline/beat_contracts.py`

**新增**：
```python
class ScenePlan(BaseModel):
    ...  # 既有字段
    predeclared_changes: PredeclaredChanges  # ⚡ NEW
```

**消费方**：
- 1C `StoryOSDelegate.validate_predeclared_changes()` 接收
- 1D API response 序列化此字段供前端展示
- 1B `SFLogParserService.match_against_predeclared()` 消费

**回归测试**：所有 Planner 测试需覆盖 predeclared_changes 必填。

### 契约 4：`MatchReport.should_retry` / `has_warnings`（1A 产出 → 1B/1C 消费）

**位置**：`domain/storyos/value_objects/predeclared.py`

**API**：
```python
@dataclass
class MatchReport:
    predeclared_total: int
    predeclared_implemented: int
    missing_changes: list[PredeclaredChange]      # → 触发 RETRY
    unexpected_records: list[SFLogRecord]         # → 仅 WARN
    match_rate: float

    @property
    def should_retry(self) -> bool:
        return len(self.missing_changes) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.unexpected_records) > 0
```

**消费方**：
- 1B `SFLogComplianceGate.evaluate(match_report, retry_count) -> ComplianceDecision`
- 1C PipelineRunner 决策树（PASS / WARN_AND_PASS / RETRY / FORCE_PASS）

### 契约 5：`AssetStatus` 12 态（1A 产出 → 全阶段消费）

**位置**：`domain/storyos/contracts.py`

**消费方**：8 entity 状态字段 + 7 cascade 规则 + 前端 `StatusBadge` 颜色映射。

**回归测试**：禁止新增状态值（需同步更新 FORBIDDEN_TRANSITIONS + 7 cascade 规则 + cascade_history schema）。

### 契约 6：8 Entity 字段（1A 产出 → 1B 消费）

**位置**：`domain/storyos/entities/{8}.py`

**公共字段**（每个 entity 必须有）：
- `id: str`（业务 ID，非自增）
- `status: AssetStatus`
- `created_chapter: int`

**消费方**：8 Registry service 用 `id` 查询 / 用 `status` 过滤 / 用 `created_chapter` 排序。

### 契约 7：`PredeclaredChange.asset_id XOR asset_pair`（1A 产出 → 1B/1C 消费）

**位置**：`domain/storyos/value_objects/predeclared.py`

**校验**：`@model_validator(mode="after")` 强制 `(self.asset_id is None) != (self.asset_pair is None)`。

**消费方**：
- 1B `SFLogActionMapper` 根据 `log_type` 决定用 asset_id 还是 asset_pair
- 1C `StoryOSDelegate.validate_predeclared_changes()` 引用存在性检查

**回归测试**：所有 PredeclaredChange 测试必须覆盖三种情况（仅 asset_id / 仅 asset_pair / 两者皆为 None 抛错 / 两者皆非 None 抛错）。

### 契约 8：`bridge_log` 事务外写入（1A 产出 schema + 1B 产出逻辑）

**位置**：`infrastructure/persistence/storyos/schemas/bridge_log_schema.py` + `application/storyos/services/evolution_bridge_service.py`

**写入时机**：`bridge_log` **不在** `transaction()` 内部写入。原因：事务内写入会随 ROLLBACK 回滚 → 失败记录丢失。

**伪代码**（1B 实施）：
```python
try:
    with dispatch.transaction() as txn:
        txn.queue_apply(evolution_apply, ...)
        txn.queue_apply(registry_apply_with_cascade, ...)
        txn.queue_apply(sflog_event_record, ...)
except BridgeError as e:
    dispatch.queue(lambda c: bridge_log_record(c, success=False, error=str(e)))  # 事务外
    raise
```

**消费方**：1D 失败排查 UI / 1E 迁移审计 / 监控系统。

---

## 依赖图与并行机会

```
```
                ┌─────────────────────────┐
                ↓                         ↓
Phase 1A Foundation              Phase 1D Frontend+API
(domain + persistence)           (待 1B API 契约冻结即可启动)
                ↓                         ↓
        Phase 1B Application ←────────────┘
        (parsers + services + bridge)
                ↓
        Phase 1C Engine Integration
        (StoryOSDelegate + 钩子 + ScenePlan 扩展)

        Phase 1E Migration Tool（完全独立，可在任意阶段开发）
```

### 阶段级依赖矩阵

| 后续阶段 \ 前置阶段 | 1A Foundation | 1B Application | 1C Engine | 1D Frontend+API | 1E Migration |
|---|---|---|---|---|---|
| 1A | — | — | — | — | — |
| 1B | ✅ 必需 | — | — | — | — |
| 1C | ✅ 必需 | ✅ 必需 | — | — | — |
| 1D | — | ✅ 必需（API 契约冻结） | ✅ 必需（ScenePlan 字段） | — | ⚠️ 部分（migration 端点联通） |
| 1E | ✅ 必需（`ForeshadowingMapper`） | ⚠️ 部分（MigrationService stub） | — | — | — |

### 任务级关键路径（1A 内部）

1A 内部有严格的串行依赖，不能在 group 间大幅并行：

```
A1 AssetStatus ─┐
A2 SFLogType   ─┤
A3 CascadeTrigger ─┼─→ B/C/D/E/F 全部依赖 contracts.py 完整
A4 FORBIDDEN  ───┤
A5 RegistryAsset ─┘
                ↓
B1-B5 Value Objects（依赖 A1-A4 枚举）
                ↓
C1-C8 Entities（依赖 B1-B5 值对象 + A1 枚举）
                ↓
D1 WriteTransaction 类 ─┐
D2 transaction()       ─┼─→ E schema 测试 + F1 迁移测试需要 WriteDispatch 完整
D3 queue_apply        ─┘
                ↓
D4 BaseRegistrySchema mixin（独立）
                ↓
E1-E3 11 Schemas（依赖 D4）
                ↓
F1 Alembic 迁移（依赖 E1-E3 schemas）
F2 CLI 脚手架（独立，仅 stub）
```

**1A 并行机会**：
- A1-A5 必须串行（5 任务）→ 然后 B1-B5 可串行（5 任务）→ 然后 C1-C8 串行（8 任务）→ 然后 D1-D3 串行（3 任务）→ 然后 E1-E3 串行（3 任务）→ 然后 F1-F2 并行（2 任务可同时）
- 实际推荐：6 阶段内 subagent 串行（保证契约），6 个 group 之间串行
- 替代：D1-D3 + D4-D5 可在 C 完成后**同时**派 2 个 subagent（前者修改 write_dispatch.py，后者创建新文件无冲突）

### 跨阶段数据流（1A → 1B → 1C → 1D）

```
1A 产出                                1B 消费
─────────────────────────────────────────────────────────────────
domain/storyos/contracts.py     →     parsers + services 全部
domain/storyos/value_objects/   →     parsers 输入/输出格式
domain/storyos/entities/        →     8 Registry 业务核心
WriteDispatch.transaction()     →     EvolutionBridgeService 单事务三操作
WriteTransaction.queue_apply()  →     bridge 三操作参数绑定
BaseRegistrySchema              →     11 表 schema 继承
11 ORM schemas + 11 mappers     →     1B 仓储层（**1B 不创建新表，只创建 Repository**）

1B 产出                                1C 消费
─────────────────────────────────────────────────────────────────
SFLogParserService              →     StoryOSDelegate.apply_post_write_results
EvolutionBridgeService          →     StoryOSDelegate.apply_post_write_results
SFLogComplianceGate             →     PipelineRunner 决策树
8 Registry Service              →     StoryOSDelegate.load_active_assets_for_context
CascadeService.simulate()       →     1D 预览 API
CircuitBreaker 多 gate 扩展     →     SFLogComplianceGate 复用实例

1C 产出                                1D 消费
─────────────────────────────────────────────────────────────────
ScenePlan.predeclared_changes   →     API response 序列化
StoryOSDelegate 3 方法          →     1D 调用触发 chapter 重写
sflog_directive 注入点          →     Prompt preview UI
```

**并行建议：**
- **1A 必须先完成**（所有其他阶段依赖 domain 类型 + persistence 表）
- **1D 可与 1B 中途并行**：1B 完成后冻结 API 契约 → 1D 前端可启动
- **1E 完全独立**：可在 1A 完成后任意时刻开始
- **测试全程并行**：每阶段内 TDD 任务自带测试

---

## 验收标准

### 功能验收（100% 必须通过）

- [ ] 11 类 SF_LOG 全部可解析（regex parser 覆盖 100% 语法）
- [ ] 6 类级联触发器全部生效（含 `CONFLICT_ESCALATED`）
- [ ] 3 类级联校验全部拦截（循环 / 禁止转换 / Twist 互斥）
- [ ] 8 个 registry CRUD 完整（创建 / 读取 / 更新 / 删除 / 列表）
- [ ] 11 类 SF_LOG → 6 个 EvolutionAction（5 类跳过）
- [ ] Bridge 双写原子性（COMMIT/ROLLBACK 全覆盖）
- [ ] 迁移幂等性（重复执行不重复插入）
- [ ] SFLogComplianceGate 4 决策（PASS / WARN / RETRY / FORCE_PASS）

### 集成验收

- [ ] 完整 happy path 端到端（Step 1-10 全部通过）
- [ ] Step 1/3/5/6 钩子正确触发
- [ ] 两级重试策略（missing → retry，unexpected → warn）
- [ ] 性能基准达标（见各子计划）

### 用户验收（Workbench 可见）

- [ ] StoryOSHub 页面可访问、可查询 8 Registry
- [ ] CascadeGraph 可视化级联路径
- [ ] SFLogInspector 显示原始 + 解析结果
- [ ] Export DOCX 不含 SF_LOG 注释，但含「叙事弧线摘要」附录

### 性能基准（跨阶段）

| 测试 | 输入 | 期望 |
|---|---|---|
| `parse_throughput` | 1000 SF_LOG | < 100ms |
| `cascade_depth_3` | 84 节点展开 | < 500ms |
| `migration_10k` | 1 万条 | < 30s |
| `bridge_full_chapter` | 100 SF_LOG + 50 cascade | < 200ms |

---

## Spec → 子计划映射（可追溯性）

每个 spec 章节锚定到具体子计划文件 + 任务编号。读者可以从 spec 反向追溯到实现任务。

### 设计层面

| Spec 章节 | 内容 | 子计划锚点 |
|---|---|---|
| §0 决策记录 | Q1-Q9 + R1-R3 | 本文件（决策记录表格） |
| §1 背景与目标 | tier_0 引入动机 | 本文件（Goal + Architecture） |
| §2 架构总览 | bounded context 划分 | 本文件（文件结构总览） |
| §2.3 Pipeline 集成 | 4 钩子分布 | 1C A1-A2 + B1-B4 + C1-C2 |
| §2.4 架构边界 | DDD 四层 | 本文件（文件结构总览） |
| §3.1 完整文件清单 | 全部新文件 | 本文件（文件结构总览） + 各子计划 Section 2 |

### 类型层面

| Spec 章节 | 内容 | 子计划锚点 |
|---|---|---|
| §3.2 AssetStatus 12 态 | 枚举 | 1A A1 |
| §3.2 PredeclaredChange | XOR 校验 | 1A B4 |
| §3.2 CascadeTrigger 6 类 | 含 `CONFLICT_ESCALATED` | 1A A3 |
| §3.2 CascadeStep | status/intensity 二选一 | 1A B2 |
| §3.2 BridgeResult | 桥接结果聚合 | 1B D1（应用层 dataclass） |
| §3.3 SF_LOG → Evolution 映射 | 6 映射 + 5 跳过 | 1B A3 |

### 持久化层面

| Spec 章节 | 内容 | 子计划锚点 |
|---|---|---|
| §3.4 数据库表（11 张） | 8 registry + 3 audit | 1A E1-E3 |
| §3.5 WriteDispatch 扩展 | transaction + queue_apply | 1A D1-D3 |
| §3.6 CircuitBreaker 多 gate | gate 参数 + 4 决策 | 1B E1 + E2 |
| 附录 C Foreshadowing 状态映射 | 旧→新 status 转换 | 1A C8 + 1E A1-A2 |

### 业务流层面

| Spec 章节 | 内容 | 子计划锚点 |
|---|---|---|
| §4.1 Happy Path 时序 | 5 步走通 | 1C C1-C2（钩子接入） + 1B D1（bridge） |
| §4.2 Cascade 规则 | 5 规则 + CONFLICT_ESCALATED | 1B C1-C3 |
| §4.3 失败模式 | 6 类错误响应矩阵 | 1A D3（事务原子性） + 1B E2（compliance gate） + 1B D2（bridge_log） |
| §4.4 两级重试策略 | missing→retry, unexpected→warn | 1A B5（MatchReport properties） + 1B E2（4 决策） |

### 错误处理 + 测试

| Spec 章节 | 内容 | 子计划锚点 |
|---|---|---|
| §5.1 错误响应矩阵 | 6 类错误记录位置 | 1A E3（bridge_log schema） + 1B D2（bridge_log 写入逻辑） |
| §5.2 Quality Monitor 6 指标 | StoryOSMetrics | 1B snapshot_projector |
| §5.3 关键测试用例 | 4 个核心测试 | 1A D3（bridge_sql_transaction） + 1B C3（cascade_invariants） + 1B E2（sflog_compliance_gate） + 1E F1（migration_idempotent） |
| §5.3 性能基准 | 4 个基准 | 1A E1-E3（schema 性能） + 1B A1（parse_throughput） + 1B C2（cascade_depth_3） + 1B D1（bridge_full_chapter） + 1E F2（migration_10k） |

### 实施计划层面

| Spec 章节 | 内容 | 子计划锚点 |
|---|---|---|
| §6.1 5 子阶段 | 1A-1E 估时 | 本文件（子计划文件表格） |
| §6.2 依赖图 | 阶段依赖 | 本文件（依赖图与并行机会） |
| §6.3 Top 5 风险 | 风险 + 缓解 | 本文件（风险 → 任务映射） |
| §6.4 验收标准 | 3 类验收 | 本文件（验收标准） |
| 附录 A 11 类 SF_LOG 语法 | 完整语法 | 1B A1（regex parser 覆盖） |
| 附录 D 51 API 端点 | 完整端点列表 | 1D A1-C3 |

---

## 顶层风险 + 缓解

| # | 风险 | 等级 | 缓解 |
|---|---|---|---|
| 1 | LLM 不稳定输出 SF_LOG | 🔴 高 | 完整示例 prompt + Provider 自适应 directive 强度 + 3 次重试 force_pass + 离线基准测试 |
| 2 | Bridge 双写并发竞争 | 🟡 中 | WriteDispatch 单写者天然串行 + per-chapter 锁 + 集成测试 |
| 3 | Migration 数据不一致 | 🟡 中 | assert_invariant 测试 + dry-run 模式 + 人工审核 + 不删旧表 |
| 4 | Cascade 性能 / 深度 | 🟡 中 | MAX_CASCADE_DEPTH=3 + 性能基准 + JSON 字段索引 + 降级策略 |
| 5 | CircuitBreaker 扩展破坏向后兼容 | 🟢 低 | 默认 gate="default" + deprecation warning + 完整回归测试 |

### 风险 → 任务映射（可执行性）

每个风险分散在多个具体任务中执行缓解：

#### 风险 #1：LLM 不稳定输出 SF_LOG（🔴 高）

**缓解分散在以下任务**：
- 1C D1：`sflog_directive` 注入点必须包含 11 类 SF_LOG 完整示例（spec 附录 A 全量）
- 1B A2：`SFLogFormatValidator` 严格校验，错一个字符即不解析
- 1B E2：`SFLogComplianceGate` 4 决策（PASS / WARN / RETRY / FORCE_PASS）
- 1B F2：`SFLogParserService.match_against_predeclared` 输出 `MatchReport` 包含 missing/unexpected 分类
- 1C C2：PipelineRunner 集成 RETRY 逻辑（最多 3 次后 FORCE_PASS）
- **跨阶段验收**：`test_sflog_compliance_rate.py` 离线基准测试，3 种 LLM provider 各跑 100 章，compliance ≥ 85%

#### 风险 #2：Bridge 双写并发竞争（🟡 中）

**缓解分散在以下任务**：
- 1A D1-D3：WriteDispatch 单写者队列（`mp.Queue` → 唯一消费者线程）
- 1A D3：⚠️ **关键** — `test_bridge_sql_transaction.py` 必须用 mock 验证 ROLLBACK 原子性
- 1B D1：`EvolutionBridgeService` 严格在 `with dispatch.transaction()` 内部调用 3 个 `queue_apply`
- 1B D2：`bridge_log` 写入**在事务外**（避免 ROLLBACK 时审计丢失）
- **跨阶段验收**：`pytest tests/integration/storyos/ -k concurrency` 全过

#### 风险 #3：Migration 数据不一致（🟡 中）

**缓解分散在以下任务**：
- 1A C8：⚠️ **关键** — Foreshadowing 实体**复制**到新位置，**不删除**旧位置
- 1A E2：`ForeshadowingMapper.convert_old_status_to_new` 静态方法（spec 附录 C 锁定映射）
- 1B F3 stub：MigrationService 接口冻结
- 1E A1-A3：完整业务逻辑 + 幂等性 + 断点续跑
- 1E F1：`test_migration_idempotent.py`（spec §5.3 锁定）— 重复执行 3 次不重复插入
- 1E F2：`test_migration_10k.py` — 1 万条 < 30s
- **跨阶段验收**：人工抽查 10 条样本，确认 100% 转换正确

#### 风险 #4：Cascade 性能 / 深度（🟡 中）

**缓解分散在以下任务**：
- 1A B3：`CascadeRules.would_create_cycle()` set 检测
- 1B C1：循环检测在 `CascadeRules.apply_to` 中
- 1B C2：`MAX_CASCADE_DEPTH = 3` 硬性截断
- 1B C3：降级策略（孤儿检查仅警告不阻断）
- **跨阶段验收**：`test_cascade_depth_3.py` 84 节点 < 500ms

#### 风险 #5：CircuitBreaker 扩展破坏向后兼容（🟢 低）

**缓解分散在以下任务**：
- 1B E1：⚠️ **关键** — 新增 `gate` 参数必须 `default="default"`，**所有现有调用方零修改**
- 1B E1：deprecation warning 当调用方未指定 gate
- 1B E2：现有 FactGuard 的 `gate='fact_guard'` 与新增 `gate='sflog_compliance'` **互不干扰**
- **跨阶段验收**：`pytest tests/ -m "not slow"` 全过（向后兼容验证）

---

## 子阶段任务规模（预估）

| 阶段 | TDD 任务数 | 文件数 |
|---|---|---|
| 1A Foundation | ~28-32 | ~35 |
| 1B Application | ~25-28 | ~20 |
| 1C Engine | ~9-10 | ~5 |
| 1D Frontend + API | ~16-18 | ~50 |
| 1E Migration | 14 + 1 验收 = 15 | ~12 |
| **合计** | **~93-103** | **~122** |

---

## 执行模式选择

本计划完成后，提供两种执行方式：

### 1. Subagent-Driven（推荐）

每个任务派遣独立 subagent，两阶段 review（实施后 + 测试后），最大化并行度与上下文隔离。适合大型项目，context 不会被超载。

**适用条件：** 任务间相互独立或契约清晰；项目体量 > 5000 LOC；需要频繁 review 介入。

### 2. Inline Execution

在当前会话内按序执行任务，checkpoint 处暂停供 review。context 占用高但反馈即时。

**适用条件：** 任务强依赖前序任务；需要实时调试或快速试错。

---

## 设计参考

完整设计 spec 见 [`../specs/2026-07-02-storyos-integration-design.md`](../specs/2026-07-02-storyos-integration-design.md)。

关键章节锚点：
- §3.1 完整文件清单（按 bounded context 分组）
- §3.2 关键类型签名（AssetStatus / PredeclaredChange / CascadeTrigger / CascadeStep / BridgeResult）
- §3.3 SF_LOG → Evolution 映射表（6 映射 + 5 跳过）
- §3.4 数据库表（11 张）
- §3.5 WriteDispatch 扩展（transaction + queue_apply）
- §3.6 CircuitBreaker 多 gate 扩展
- §4.1 Happy Path 时序图
- §4.2 Cascade 规则表
- §4.4 两级重试策略
- 附录 A 11 类 SF_LOG 完整语法

---

## 进度追踪

| 子阶段 | 文件 | 状态 | 任务细节 |
|---|---|---|---|
| 1A Foundation | [`2026-07-02-storyos-phase-1a-foundation.md`](./2026-07-02-storyos-phase-1a-foundation.md) | 框架已建 | 28 任务细粒度 TDD 骨架已写完 |
| 1B Application | [`2026-07-02-storyos-phase-1b-application.md`](./2026-07-02-storyos-phase-1b-application.md) | 框架已建 | 18 任务分组占位，等 1A 完成后细化 |
| 1C Engine | [`2026-07-02-storyos-phase-1c-engine.md`](./2026-07-02-storyos-phase-1c-engine.md) | 框架已建 | 9 任务分组占位，等 1A+1B 完成后细化 |
| 1D Frontend + API | [`2026-07-02-storyos-phase-1d-frontend-api.md`](./2026-07-02-storyos-phase-1d-frontend-api.md) | 框架已建 | 17 任务分组占位，等 1B API 契约冻结后细化 |
| 1E Migration | [`2026-07-02-storyos-phase-1e-migration.md`](./2026-07-02-storyos-phase-1e-migration.md) | 框架已建 | 7 任务分组占位，等 1A ForeshadowingMapper 后细化 |

**索引扩展完成度**：
- [x] 文件结构总览（按 DDD 层）— 已加入 7 个层（Domain/Application/Infrastructure/Interfaces/Engine/Frontend/Scripts）
- [x] 跨阶段类型契约 — 已锁定 8 个关键接口（WriteDispatch/CircuitBreaker/ScenePlan/MatchReport/AssetStatus/Entity 字段/PredeclaredChange/bridge_log）
- [x] Spec → 子计划映射 — 5 个分类（设计/类型/持久化/业务流/错误测试/实施计划）共 30+ 反向追溯项
- [x] 依赖图与并行机会 — 已加入阶段级依赖矩阵 + 1A 内部任务级关键路径 + 跨阶段数据流
- [x] 风险 → 任务映射 — 5 个 Top 风险分散到具体任务