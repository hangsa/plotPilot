# Phase 2A — Tier 0 SF_LOG Fact Guard Design

> **修订日期**：2026-07-07
> **修订人**：claude-opus-4.7 (with hangsa review)
> **supersedes**：`2026-07-07-prompt-fusion-design.md` Phase 2A 段（原 spec Q1-Q9 中与 v1.2 实际行为冲突的部分）

## 0. 背景

`docs/superpowers/specs/2026-07-07-prompt-fusion-design.md` 提出 Phase 2A 引入 Tier 0 fact_guard（确定性 Python 护栏）+ SF_LOG 6 类减法 + character.taboos + cost_system + PromptGateway + 6 个 anti-ai-* 降级。但与 v1.2 已发布代码对账后发现：

| 原 spec 假设 | v1.2 实际状态 | 处理 |
|---|---|---|
| 减法到 6 类 SF_LOG | 11 类已上线（`domain/storyos/contracts.py:SFLogType`） | **保留 11 类** |
| character.taboos 新字段 | `moral_taboos: List[str]` 已存在 | **延后到 Phase 2B** |
| worldbuilding.power_system 嵌套结构 | `power_system: str = ""` 平字段 | **延后到 Phase 2B** |
| PromptGateway 中央路由 | 不存在 | **延后到 Phase 2B/2C** |
| 6 个 anti-ai-* 节点降级 | 仍在 Tier 1 跑 | **延后到 Phase 2B** |

**Phase 2A 重定义为**：仅交付 **Tier 0 SF_LOG fact_guard**（post-write 同步门 + 3 attempt + force-pass），输入是 v1.2 现有 11 类 SFLogType，输出 GuardReport。其他 4 块推迟到 Phase 2B/2C。

---

## 1. 架构

四层 + 一个配置：

```
engine/pipeline/steps/sf_log_fact_guard.py  ← pipeline hook (Step 5.5, post-write sync)
        │
        ▼
application/sf_log/fact_guard_service.py     ← service facade (orchestrate 3 attempts)
        │
        ▼
application/sf_log/regex_engine.py          ← loads config/fact_guard_rules.yaml
        │
        ▼  (12 rule blocks)
config/fact_guard_rules.yaml                  ← 12 rule blocks (1 per SFLogType + 1 registry)
```

**为什么单 YAML regex 引擎而不是 11 handler**：用户选择单点可调优；规则 disable = 注释一行；非正则逻辑走 `python_callable` 逃生口（3 条规则用）。

**为什么 post-write 同步门**：失败可同步重写 SF_LOG 块，3 attempt 后强制 pass，章节不卡。

---

## 2. 数据契约

### 2.1 输入

```python
@dataclass(frozen=True)
class FactGuardInput:
    chapter_id: str
    chapter_text: str                    # prose body
    sflog_records: list[SFLogRecord]     # v1.2 现有类型
    bible_snapshot: ChapterBibleContext  # 只读快照
```

### 2.2 输出

```python
class Severity(str, Enum):
    HARD = "hard"      # 必须修正（或 force-pass 后进 warnings）
    SOFT = "soft"      # 仅警告

@dataclass(frozen=True)
class GuardHit:
    rule_id: str
    sflog_id: str | None
    severity: Severity
    message: str
    matched_text: str | None = None

@dataclass
class GuardReport:
    passed: bool
    forced_pass: bool                    # True when attempt 3 still has HARD hit
    attempt: int                         # 1 | 2 | 3
    hits: list[GuardHit]
```

`passed` 语义：所有 HARD 命中已修正（attempt 1/2 重写后无 HARD 命中），或 attempt 3 后强制 pass。SOFT 命中不阻断 `passed`。

---

## 3. 规则 Schema

`config/fact_guard_rules.yaml`：

```yaml
version: 2a-1
defaults:
  severity_on_miss: hard
  text_window_chars: 200
rules:
  - id: <rule_id>
    applies_to: <SFLogType enum value>
    severity: hard | soft
    description: <str>
    text_window_chars: <int, override default>
    
    # 三选一：
    pattern: '<single regex>'                       # 简单正则
    patterns:                                        # 多正则 OR
      - name: <str>
        regex: '<regex>'
    python_callable: '<module.func>'                # 逃生口：自定义 Python 函数
```

**三种 pattern 风味**：
1. `pattern` — 单正则
2. `patterns` — 多正则，任一命中即 hit
3. `python_callable` — 非正则逻辑（如 knowledge/registry 查表），签名 `(input: FactGuardInput, record: SFLogRecord) -> list[GuardHit]`

---

## 4. 12 条规则骨架

| # | rule_id | applies_to | severity | pattern 意图 |
|---|---|---|---|---|
| 1 | `character_relation.no_self_loop` | CHARACTER_RELATION_CHANGE | hard | subject == object |
| 2 | `character_location.no_instant_teleport` | CHARACTER_LOCATION_CHANGE | hard | 在 ±200 chars 内检测瞬移/传送/闪现 类禁词 |
| 3 | `character_location.continuity` | CHARACTER_LOCATION_CHANGE | hard | 连续 location 必须在 `worldbuilding.links` 可达（python_callable） |
| 4 | `character_physical.no_undo_without_cause` | CHARACTER_PHYSICAL_CHANGE | hard | 失去的身体部位恢复但无 cause 字段 |
| 5 | `character_emotion.amplitude_cap` | CHARACTER_EMOTION | soft | 单章 emotion_level delta > 2 |
| 6 | `knowledge_gain.no_omniscience` | KNOWLEDGE_GAIN | hard | 知识赋予方不在 scene.cast 中（python_callable） |
| 7 | `conflict_escalate.no_repeat` | CONFLICT_ESCALATE | soft | 同 conflict_id 在单章 escalate >1 次 |
| 8 | `mystery_clue.no_premature_reveal` | MYSTERY_CLUE | hard | mystery_id 在 `expected_paid_chapter` 之前 reveal（python_callable） |
| 9 | `twist_reveal.no_orphan` | TWIST_REVEAL | hard | twist_id 必须在 foreshadowing/twist registry 存在 |
| 10 | `expectation_fulfill.scope` | EXPECTATION_FULFILL | soft | expect_id 必须存在且未被双 fulfill |
| 11 | `goal_milestone.no_skip` | GOAL_MILESTONE | hard | 相邻 milestone 必须有 ≥1 章间隔 |
| 12 | `registry_create.uniqueness` | REGISTRY_CREATE | hard | (s, p, o) 三元组不在 registry 中重复 |

**规则分布**：8 hard + 4 soft = 12 规则覆盖 11 个 SFLogType（REGISTRY_CREATE 单独一条因全局唯一性约束）。

---

## 5. 重试与强制 Pass 语义

```
attempt 1: run engine(prose_v1, sflog_records_v1)
  if no HARD hit → passed=True, attempt=1, done
  
  HARD hit found:
    rewrite_only_sflog_block(prose_v1, hits) → sflog_records_v2 (prose body unchanged)
    
attempt 2: run engine(prose_v1, sflog_records_v2)
  if no HARD hit → passed=True, attempt=2, done
  
  HARD hit found:
    rewrite_only_sflog_block(prose_v1, hits) → sflog_records_v3
    
attempt 3: run engine(prose_v1, sflog_records_v3)
  if no HARD hit → passed=True, attempt=3, done
  
  HARD hit found:
    passed=True, forced_pass=True, attempt=3
    append all hits to chapter.warnings (NEW field)
```

**关键不变式**：`prose body` 在三次 attempt 中**不变**，只重写 SF_LOG 块。重写 CPMS 节点 = 现有 `sf-log-rewrite-with-hints`（已有 v1.2 节点，加 hit context 输入）。

**Chapter 状态变更**：现有 `Chapter` 实体增加 `warnings: list[GuardHit]` 字段（nullable, default=[]）。**注**：v1.2 当前没有 `drift_warnings` 字段——这是本 spec 新引入的字段，作为 fact_guard 输出的载体。新增 `GET /api/v1/chapters/{id}/warnings` 端点（仅读，列表返回 GuardHit 摘要）。

---

## 6. Pipeline Hook 集成点

**位置**：Step 5.5，插在 `engine/pipeline/steps/sf_log_extract.py` (Step 5) 与 `engine/pipeline/steps/apply_state.py` (Step 6) 之间。

**Step 5.5 输入/输出**：
```python
def step_sf_log_fact_guard(chapter_draft, sflog_records, bible_snapshot) -> StepResult:
    report = fact_guard_service.evaluate(
        FactGuardInput(
            chapter_id=chapter_draft.id,
            chapter_text=chapter_draft.body,
            sflog_records=sflog_records,
            bible_snapshot=bible_snapshot,
        )
    )
    if not report.passed and not report.forced_pass:
        # 触发 sf-log-rewrite-with-hints 重写 attempt 2/3
        sflog_records_v2 = rewrite_sflog_block(sflog_records, report.hits)
        # 内部循环 3 次，超出 → forced_pass
    chapter_draft.warnings = report.hits  # 即使 passed=True 也保留 soft hits
    return StepResult(passed=report.passed, artifacts={"sflog_records": final_records})
```

**未通过时的回退**：如果 3 次 attempt 后 forced_pass=true，pipeline **不中断**，Step 6 继续 apply-state。warnings 字段累积给后续章节上下文（影响 ChapterBibleContext 的下一章构造）。

---

## 7. 文件计划

```
config/fact_guard_rules.yaml                              (NEW, 12 rule blocks)
domain/sf_log/__init__.py                                 (NEW)
domain/sf_log/guard_report.py                             (NEW: GuardReport, GuardHit, Severity)
application/sf_log/__init__.py                            (NEW)
application/sf_log/fact_guard_service.py                  (NEW: orchestrate 3 attempts)
application/sf_log/regex_engine.py                        (NEW: loads YAML, evaluates single chapter)
application/sf_log/bible_snapshot.py                      (NEW: ChapterBibleContext read-only)
application/sf_log/callables/__init__.py                  (NEW: python_callable registry)
application/sf_log/callables/knowledge_omniscience.py    (NEW: rule 6)
application/sf_log/callables/location_continuity.py      (NEW: rule 3)
application/sf_log/callables/mystery_reveal_window.py     (NEW: rule 8)
engine/pipeline/steps/sf_log_fact_guard.py                (NEW: Step 5.5)
domain/novel/entities/chapter.py                          (MODIFY: add warnings field)
interfaces/api/v1/chapters.py                             (MODIFY: GET /chapters/{id}/warnings)

tests/unit/sf_log/test_regex_engine.py                    (NEW: 36 cases, 12 rules × 3)
tests/unit/sf_log/test_fact_guard_service.py              (NEW: 3-attempt + force-pass)
tests/integration/sf_log/test_sf_log_fact_guard_hook.py   (NEW: pipeline Step 5.5)
```

**文件总数**：12 个新文件 + 2 个修改 = 14 个变更。

---

## 8. 测试计划

**单元测试** (target ≥ 80% coverage on `application/sf_log/`):
- `test_regex_engine.py`：12 规则 × (happy + boundary + hit) = 36+ 单元 case
- `test_fact_guard_service.py`：5 case — 1st pass clean / 1st fail→2nd pass / 1st-2nd-3rd fail→force-pass / 规则 disabled / regex flag 关

**集成测试**：
- `test_sf_log_fact_guard_hook.py`：3 case — Step 5.5 全通过 / 触发 sf-log-rewrite-with-hints 重写 / 3 次失败 → chapter.warnings 累积
- `test_registry_create_uniqueness_e2e.py`：1 case — 端到端 (s, p, o) 重复时阻断

**回归**：
- 复用 v1.2 `tests/regression/test_chapter_extraction.py` 现有 20 章样本，扩展 `fact_guard_pass_rate` 字段
- 1st-attempt pass rate ≥ 70% 是验收阈值

---

## 9. 验收指标

| 指标 | 目标 | 测量方法 |
|---|---|---|
| 单章 fact_guard 耗时 P95 | < 100ms | `tests/performance/test_fact_guard_latency.py` |
| 1st-attempt pass rate | ≥ 70% | 20 章样本回归 |
| HARD false-pass 率（attempt 3 后） | 0 例 | 20 章样本 + 人工 spot-check 5 章 |
| SOFT 命中误报率 | < 10% | 50 章样本 + 人工标注 |
| Python 3.9 兼容 | 全过 | `pytest tests/unit/sf_log/` 无 PEP 604 报错 |
| 现有 v1.2 测试零回归 | 1915 passed 不变 | `pytest tests/ -m "not slow"` 全过 |

**Phase 2A 完成判定**：上述 6 项全过 + 1E migration 端点仍 200/404 + 1D 验收清单无回归。

---

## 10. 风险

| 风险 | 等级 | 触发条件 | 缓解 |
|---|---|---|---|
| 中文正则误报（rule 2 瞬移） | 🟡 中 | 玄幻/历史对话中讨论传送概念 | text_window_chars 限 ±200；severity=hard 时仅作 hit 不阻断（force-pass 后警告） |
| Rule 6 全知依赖 scene.cast 准确 | 🟡 中 | SF_LOG 抽取阶段 cast 错则级联 | 集成测试必须先校验 cast 准确 |
| 3 attempt 重写 SF_LOG 块后 prose 不一致 | 🟡 中 | SF_LOG 与正文矛盾无法只改 SF_LOG 解决 | attempt 3 force-pass + warnings；Phase 2B 可升级为 prose-level rewrite |
| YAML 配置 hot-reload 安全 | 🟢 低 | 用户编辑时语法错 | 启动期 YAML load fail → fail-fast，禁止运行时 hot-reload |
| Phase 1E migration 并发冲突 | 🟢 低 | migration 期间同时跑 fact_guard | 严格串行：1E migration 已完成（commit 4eb1acf9），Phase 2A 才启动 |

---

## 11. 与原 spec 的冲突已解决

| 原 spec | 修订 | 理由 |
|---|---|---|
| Q2 减法到 6 类 | **保留 11 类** | v1.2 已上线 11 类，减法是破坏性 |
| Q3 重试 2 次 | **保持 3 次** | 用户认可 |
| Q4 character.taboos 必填 | **推迟到 2B** | Phase 2A 范围聚焦 |
| Q5 cost_system 题材适配 | **推迟到 2B** | 同上 |
| Q6 anti-ai-* 降级 | **推迟到 2B** | 同上 |
| Q7 PromptGateway | **推迟到 2B/2C** | Tier 0 不需要 LLM 路由 |
| Q9 前端硬约束 UI | **推迟到 2B** | Phase 2A 仅后端验证链 |

原 spec `2026-07-07-prompt-fusion-design.md` Phase 2A 段（§4.1）由本 spec 替换。Phase 2B/2C 仍按原 spec 节奏。

---

## 12. Phase 2B 路径（已识别的下阶段）

- `character.taboos`：重命名 `moral_taboos` + 加 `unknown_to_character`
- `worldbuilding.power_system`：加嵌套 `PowerSystem { name, stages, cost_system, ceilings }` 与现有字符串并存
- `PromptGateway`：4-Tier 模型路由
- 6 个 anti-ai-* 节点降级到 T2
- 前端硬约束违反 UI

每个都是独立 sub-spec，按 2A 节奏（4 周）继续。