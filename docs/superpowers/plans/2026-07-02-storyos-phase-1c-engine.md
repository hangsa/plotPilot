# StoryOS Phase 1C — Engine Integration 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Parent Plan:** [`2026-07-02-storyos-integration.md`](./2026-07-02-storyos-integration.md)
**Spec Reference:** [`../specs/2026-07-02-storyos-integration-design.md`](../specs/2026-07-02-storyos-integration-design.md) §2.3, §3.1, §4.1, §4.3
**Sub-Spec Reference:** [`../specs/2026-07-02-storyos-asset-field-spec.md`](../specs/2026-07-02-storyos-asset-field-spec.md)
**Phase Scope:** StoryOSDelegate + 4 钩子（Step 1/3/5/6）+ ScenePlan.predeclared_changes 扩展 + sflog_directive 注入
**LOC Target:** ~550
**Estimated Tasks:** 9
**Estimated Duration:** 3 天
**前置依赖:** Phase 1A + Phase 1B 全部完成

---

## 0. 背景与目标

### 0.1 阶段目标

将 1A/1B 完成的领域层（`domain/storyos/`）与应用服务（`application/storyos/`）接入到引擎主流程 `engine/pipeline/base.py::BaseStoryPipeline`（10 步管线），让 StoryOS 在生产写作流程中"活"起来。

### 0.2 与 spec §2.3 钩子映射

spec §2.3 锁定 6 个钩子点（编号 1/2/3/4/5/6），**不是** BaseStoryPipeline 的步骤编号。映射如下：

| Spec 钩子编号 | BaseStoryPipeline 步骤 | 说明 |
|---|---|---|
| Step 1: context-load | `_step_build_context` | 调用 `delegate.load_active_assets_for_context`，把活跃资产注入 LLM 上下文 |
| Step 2: plan-beats | `_step_prepare_chapter_plan` | Planner 输出 `ScenePlan.predeclared_changes` |
| Step 3: pre-write gate | `_step_prepare_chapter_plan` 末尾 | 调用 `delegate.validate_predeclared_changes` |
| Step 4: compose | `_step_generate` | 注入 `sflog_directive` 到 prompt |
| Step 5: post-write gate | `_step_validate_content` 末尾 | 调用 `parser.parse → validate_format → match_against_predeclared` |
| Step 6: apply-state | `_step_save_chapter` 与 `_step_run_post_commit` 之间 | 调用 `delegate.apply_post_write_results` 走 WriteDispatch 单事务 |

### 0.3 关键设计决策

1. **StoryOSDelegate 是唯一引擎接入点**（spec §3.1 ⚡ 标记）：3 方法合一 `load_active_assets_for_context` / `validate_predeclared_changes` / `apply_post_write_results`。所有钩子都通过 delegate 调用，不在 BaseStoryPipeline 内直接 import 应用服务。
2. **降级策略**：delegate 任何方法失败时，pipeline 不应中断（spec §4.3 失败模式 F 软失败）。`ctx.storyos_failed` 列表记录降级信息，`_step_finalize` 时落到 `audit_snapshot`。
3. **ScenePlan 是新增类型**（spec §3.1 锁定字段）：由于 `engine/pipeline/beat_contracts.py` 当前没有 ScenePlan 类，1C 引入最小化的 ScenePlan dataclass（仅含 spec 必需的 `predeclared_changes` 字段 + `beats` 引用 + `chapter_id` + `outline` 摘要），不破坏现有 `serialize_beats_for_shared_state` 行为。
4. **sflog_directive 是 YAML 注入点**（spec §3.1 锁定）：在 `infrastructure/ai/prompt_packages/nodes/chapter-prose-generation/package.yaml` 新增 `sflog_directive` 变量（11 类 SF_LOG 提示 + 3 个示例）。注意：1C 计划原始占位符写的是 `scene-writing/package.yaml`，**实际 PlotPilot 不存在该节点**。经过 `ls` 验证，最接近 scene-writing 语义且由 ProseComposer 消费的节点是 `chapter-prose-generation`。实施时使用此节点。
5. **predeclared validation 用 registry 查找而非 cascade.simulate**（1C 重新设计）：`validate_predeclared_changes` 通过 `registry_services: dict[str, GenericRegistryService]` 字典按 `asset_type` 查 `svc.get(asset_id)` 验证存在性（1B `KeyError` 语义）。**不**用 `cascade.simulate`，因为 simulate 检查 cascade 深度/循环，自循环会永远返回 `would_block=True`，语义错误。`cascade_service` 仍保留为可选附加校验，但不在 1C 必填范围。

### 0.4 与 1A/1B 边界

| 1A 产出 | 1C 消费方式 |
|---|---|
| `PredeclaredChange` / `PredeclaredChanges` | ScenePlan.predeclared_changes 字段类型 |
| `MatchReport` | StoryOSDelegate.apply_post_write_results 返回的中间结构 |
| `CascadeRules` / `CascadeStep` / `CascadeTrigger` | 仅在 CascadeService 内部使用，1C 不直接接触 |

| 1B 产出 | 1C 消费方式 |
|---|---|
| `ActiveAssetsContext` / `ActiveAssetsService` | `delegate.load_active_assets_for_context` 返回值 |
| `PredeclaredValidation` | `delegate.validate_predeclared_changes` 返回值 |
| `BridgeResult` | `delegate.apply_post_write_results` 返回值 |
| `SFLogParserService`（3 方法） | `apply_post_write_results` 内部编排 parse/validate/match |
| `EvolutionBridgeService.apply_sflog_batch` | `apply_post_write_results` 内部调用 |
| `SFLogComplianceGate` | `apply_post_write_results` 失败时调用 `record_force_pass` |
| `GenericRegistryService`（8 个 1B 注册服务） | `delegate.validate_predeclared_changes` 通过 `registry_services` 字典注入，按 `asset_type` 取对应 service 做 `get(asset_id)` 存在性校验（1A 锁定 KeyError 语义） |

### 0.5 测试覆盖目标

- `tests/dag/storyos/` — 4 钩子集成 + 两级重试（spec §5.3 锁定）
- `tests/unit/engine/runtime/test_storyos_delegate.py` — 12 测试（3 B1 + 5 B2 + 4 B3）
- `tests/unit/engine/pipeline/test_scene_plan.py` — ScenePlan dataclass 单元测试
- mock 整个 delegate，验证 PipelineRunner 在 Step 1/3/5/6 正确调用
- 验证失败时不阻断后续步骤（降级到 warn）

---

## 1. 文件结构

### 1.1 新增文件

```
engine/pipeline/beat_contracts.py            # 修改: 新增 ScenePlan dataclass + predeclared_changes 字段
engine/runtime/storyos_delegate.py            # 新增: 3 方法 delegate
config/prompt_packages/nodes/chapter-prose-generation/package.yaml  # 修改: 新增 sflog_directive 变量
```

### 1.2 修改文件

```
engine/pipeline/context.py                   # 修改: PipelineContext 新增 storyos_* 字段
engine/pipeline/base.py                      # 修改: 4 钩子集成点（_step_build_context / _step_prepare_chapter_plan / _step_validate_content / _step_save_chapter）
engine/runtime/runner.py                     # 修改: DI 注入 StoryOSDelegate
engine/runtime/daemon_host.py                # 修改: 注入 storyos_delegate 参数
```

### 1.3 测试文件

```
tests/unit/engine/pipeline/
  test_scene_plan.py                         # ScenePlan dataclass 单元测试
tests/unit/engine/runtime/
  test_storyos_delegate.py                   # StoryOSDelegate 3 方法单元测试
tests/dag/storyos/
  test_hook_step1_context_load.py            # Step 1 钩子集成测试
  test_hook_step3_pre_write_gate.py          # Step 3 钩子集成测试
  test_hook_step5_post_write_gate.py         # Step 5 钩子集成测试
  test_hook_step6_apply_state.py             # Step 6 钩子集成测试
  test_pipeline_degraded_when_delegate_fails.py  # 降级策略测试
```

### 1.4 不修改（确认边界）

- `engine/pipeline/prose_composer.py` — ProseComposer 不动；sflog_directive 通过 `ctx.metadata` 传入
- `application/storyos/` — 1B 已完成，1C 只消费不修改
- `domain/storyos/` — 1A 已完成，1C 只消费不修改

---

## 2. 任务分组

```
Group A: ScenePlan 扩展 (2 任务)
  - A1: ScenePlan dataclass + predeclared_changes 字段
  - A2: ScenePlan 序列化进 shared state

Group B: StoryOSDelegate 实现 (3 任务)
  - B1: load_active_assets_for_context
  - B2: validate_predeclared_changes
  - B3: apply_post_write_results

Group C: 4 钩子接入 (2 任务)
  - C1: PipelineRunner 在 Step 1/3/5/6 调用 delegate + 降级处理
  - C2: DI 装配（runner + daemon_host 注入 storyos_delegate）

Group D: Prompt 注入点 (1 任务)
  - D1: chapter-prose-generation/package.yaml 新增 sflog_directive

总计 8 主任务 + 1 集成测试任务 = 9 任务。
```

---

## 3. 任务详化

### Group A: ScenePlan 扩展

#### Task A1: ScenePlan dataclass + predeclared_changes 字段

**Files:**
- Modify: `engine/pipeline/beat_contracts.py:1-66`（在 `serialize_beats_for_shared_state` 之前新增 `ScenePlan` 类）
- Create: `tests/unit/engine/pipeline/test_scene_plan.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/engine/pipeline/test_scene_plan.py
from engine.pipeline.beat_contracts import ScenePlan
from domain.storyos.value_objects.predeclared import (
    PredeclaredChange, PredeclaredChanges,
)
from domain.storyos.contracts import SFLogType


def test_scene_plan_minimal():
    """ScenePlan 最小构造：仅 chapter_id + outline"""
    plan = ScenePlan(chapter_id=5, outline="本章主角踏入禁地")
    assert plan.chapter_id == 5
    assert plan.outline == "本章主角踏入禁地"
    assert plan.predeclared_changes == PredeclaredChanges()
    assert plan.beats == []


def test_scene_plan_with_predeclared_changes():
    """ScenePlan.predeclared_changes 字段（spec §3.1 ⚡ 锁定）"""
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery", asset_id="m1",
        ),
        PredeclaredChange(
            log_type=SFLogType.CONFLICT_ESCALATE,
            asset_type="conflict", asset_id="c1",
        ),
    ])
    plan = ScenePlan(
        chapter_id=5,
        outline="",
        predeclared_changes=predeclared,
    )
    assert plan.predeclared_changes is predeclared
    assert len(plan.predeclared_changes) == 2


def test_scene_plan_to_shared_state_dict():
    """ScenePlan.to_shared_state_dict 序列化（供 checkpoint / BFF API 使用）"""
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery", asset_id="m1",
        ),
    ])
    plan = ScenePlan(
        chapter_id=5,
        outline="outline text",
        predeclared_changes=predeclared,
    )
    state = plan.to_shared_state_dict()
    assert state["chapter_id"] == 5
    assert state["outline"] == "outline text"
    assert state["predeclared_changes"] == [
        {
            "log_type": "mystery_clue",
            "asset_type": "mystery",
            "asset_id": "m1",
            "asset_pair": None,
            "expected_params": {},
        }
    ]


def test_scene_plan_is_frozen():
    """ScenePlan 不可变（spec §3.2 类似 MatchReport 风格）"""
    from dataclasses import FrozenInstanceError
    plan = ScenePlan(chapter_id=5, outline="")
    import pytest
    with pytest.raises(FrozenInstanceError):
        plan.chapter_id = 6  # type: ignore[misc]
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ImportError: cannot import name 'ScenePlan'`

Run: `pytest tests/unit/engine/pipeline/test_scene_plan.py -v`
Expected: FAILED with `ImportError`

- [ ] **Step 3: 实现** — 修改 `engine/pipeline/beat_contracts.py:1-12`，在 `serialize_beats_for_shared_state` 之前新增 ScenePlan：

```python
# engine/pipeline/beat_contracts.py 新增（顶部 import 之后）

from __future__ import annotations
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, List, Optional

from domain.storyos.value_objects.predeclared import (
    PredeclaredChange, PredeclaredChanges,
)


@dataclass(frozen=True)
class ScenePlan:
    """章节执行剧本（spec §3.1 ⚡ 锁定 predeclared_changes 字段）。

    包含：
    - chapter_id: 章节编号
    - outline: 章节大纲（来自 Planner）
    - beats: 微观节拍列表（保留 beat_contracts 现有能力）
    - predeclared_changes: 预声明的 SF_LOG 操作（spec §4.1 Step 2）
    """
    chapter_id: int
    outline: str
    beats: List[Any] = field(default_factory=list)
    predeclared_changes: PredeclaredChanges = field(
        default_factory=PredeclaredChanges
    )

    def to_shared_state_dict(self) -> dict:
        """序列化为 dict（供 checkpoint / BFF API response / 1D StoryOSHub 使用）"""
        return {
            "chapter_id": self.chapter_id,
            "outline": self.outline,
            "beats": serialize_beats_for_shared_state(self.beats) if self.beats else [],
            "predeclared_changes": [
                _predeclared_to_dict(p) for p in self.predeclared_changes
            ],
        }


def _predeclared_to_dict(p: PredeclaredChange) -> dict:
    """PredeclaredChange → dict（保留 1A spec §3.2 字段语义）

    PredeclaredChange 字段（1A 锁定）：
        log_type, asset_type, asset_id, asset_pair, expected_params
    """
    return {
        "log_type": p.log_type.value,
        "asset_type": p.asset_type,
        "asset_id": p.asset_id,
        "asset_pair": list(p.asset_pair) if p.asset_pair else None,
        "expected_params": dict(p.expected_params),
    }
```

并在文件底部（`_merge_entity_manifest` 之后）添加 ScenePlan 的导入支持（如已有 `__all__` 列表则加入）。

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed

Run: `pytest tests/unit/engine/pipeline/test_scene_plan.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add engine/pipeline/beat_contracts.py tests/unit/engine/pipeline/test_scene_plan.py
git commit -m "feat(engine): add ScenePlan dataclass with predeclared_changes field (spec §3.1)"
```

---

#### Task A2: ScenePlan 接入 ctx.scene_plan 字段

**Files:**
- Modify: `engine/pipeline/context.py:62-65`（在 `beats` 字段后新增 `scene_plan` 字段）
- Modify: `engine/pipeline/context.py:141-163`（`inject` 方法不需修改，依赖 `_dependencies` 兜底）
- Create: `tests/unit/engine/pipeline/test_context_scene_plan.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/engine/pipeline/test_context_scene_plan.py
from engine.pipeline.context import PipelineContext
from engine.pipeline.beat_contracts import ScenePlan


def test_context_default_scene_plan_is_none():
    """PipelineContext 默认 scene_plan = None（不破坏现有管线）"""
    ctx = PipelineContext(novel_id="n1", chapter_number=5)
    assert ctx.scene_plan is None


def test_context_set_scene_plan_via_attribute():
    """可以直接赋值 scene_plan（spec §3.1 字段在 Step 2 末尾设置）"""
    from domain.storyos.value_objects.predeclared import PredeclaredChanges
    ctx = PipelineContext(novel_id="n1", chapter_number=5)
    plan = ScenePlan(
        chapter_id=5,
        outline="outline",
        predeclared_changes=PredeclaredChanges(),
    )
    ctx.scene_plan = plan
    assert ctx.scene_plan is plan
    assert ctx.scene_plan.chapter_id == 5
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `AttributeError: 'PipelineContext' object has no attribute 'scene_plan'`

Run: `pytest tests/unit/engine/pipeline/test_context_scene_plan.py -v`
Expected: FAILED with `AttributeError`

- [ ] **Step 3: 实现** — 修改 `engine/pipeline/context.py:62-65`，在 `beats` 字段之后添加：

```python
# engine/pipeline/context.py（修改：line 62 之后新增字段）

    # ═══ 步骤3产出：导演剧本 ═══
    script: str = ""                               # 六模块导演剧本文本
    beat_sheet: Optional[Any] = None             # 规划阶段的 BeatSheet（输入，保留兼容）
    beats: List[Any] = field(default_factory=list)  # 微观节拍 / 写作包
    scene_plan: Optional[ScenePlan] = None       # 章节执行剧本（spec §3.1，含 predeclared_changes）
```

并在文件顶部 import：

```python
# engine/pipeline/context.py（顶部 import 区）
from engine.pipeline.beat_contracts import ScenePlan
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed

Run: `pytest tests/unit/engine/pipeline/test_context_scene_plan.py -v`
Expected: 2 passed

- [ ] **Step 5: 验证现有管线不破坏** — 运行所有现有 pipeline 测试

Run: `pytest tests/unit/engine/ -v -k "context or pipeline"`
Expected: 全部通过（无回归）

- [ ] **Step 6: Commit**

```bash
git add engine/pipeline/context.py tests/unit/engine/pipeline/test_context_scene_plan.py
git commit -m "feat(engine): add scene_plan field to PipelineContext (1C A2)"
```

---

### Group B: StoryOSDelegate 实现

#### Task B1: load_active_assets_for_context

**Files:**
- Create: `engine/runtime/storyos_delegate.py`
- Create: `tests/unit/engine/runtime/test_storyos_delegate.py`

- [ ] **Step 1: 写失败测试**（spec §3.1 锁定 3 方法之一）

```python
# tests/unit/engine/runtime/test_storyos_delegate.py
from unittest.mock import MagicMock
from engine.runtime.storyos_delegate import StoryOSDelegate
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext


def test_load_active_assets_for_context_delegates_to_service():
    """Step 1 钩子: delegate.load_active_assets_for_context → ActiveAssetsService.build_context"""
    active_svc = MagicMock()
    expected = ActiveAssetsContext(novel_id="n1", chapter_id=5)
    active_svc.build_context.return_value = expected

    delegate = StoryOSDelegate(active_assets_service=active_svc)
    result = delegate.load_active_assets_for_context("n1", 5)
    assert result is expected
    active_svc.build_context.assert_called_once_with("n1", 5)


def test_load_active_assets_for_context_returns_empty_on_service_none():
    """降级策略: service 未注入时返回空 ActiveAssetsContext（不抛异常）"""
    delegate = StoryOSDelegate(active_assets_service=None)
    result = delegate.load_active_assets_for_context("n1", 5)
    assert result.novel_id == "n1"
    assert result.chapter_id == 5
    assert result.total_active == 0


def test_load_active_assets_for_context_returns_empty_on_service_failure():
    """降级策略: service 抛异常时返回空 ActiveAssetsContext + 记录到 ctx（spec §4.3 F）"""
    active_svc = MagicMock()
    active_svc.build_context.side_effect = RuntimeError("db down")
    delegate = StoryOSDelegate(active_assets_service=active_svc)
    result = delegate.load_active_assets_for_context("n1", 5)
    assert result.novel_id == "n1"
    assert result.total_active == 0
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`

Run: `pytest tests/unit/engine/runtime/test_storyos_delegate.py -v`
Expected: FAILED with `ModuleNotFoundError: No module named 'engine.runtime.storyos_delegate'`

- [ ] **Step 3: 实现** — 创建 `engine/runtime/storyos_delegate.py`：

```python
"""StoryOSDelegate — 引擎接入点（spec §3.1 锁定 3 方法合一）。

spec §2.3 钩子映射：
- Step 1 (context-load) → load_active_assets_for_context
- Step 3 (pre-write gate) → validate_predeclared_changes
- Step 5-6 (post-write gate + apply-state) → apply_post_write_results

降级策略：所有方法失败时返回安全的空值，由 PipelineRunner 负责记录到
ctx.storyos_failed 列表，spec §4.3 失败模式 F。
"""
from __future__ import annotations

import logging
from typing import Any

from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.circuit_breaker_integration import (
    SFLogComplianceGate, ComplianceDecision,
)
from application.storyos.services.evolution_bridge_service import (
    EvolutionBridgeService, EvolutionBridgeError,
)
from application.storyos.services.sf_log_parser_service import SFLogParserService
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext
from application.storyos.value_objects.bridge_result import BridgeResult
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.predeclared import PredeclaredChanges

logger = logging.getLogger(__name__)


class StoryOSDelegate:
    """StoryOS 引擎接入点（spec §3.1）"""

    def __init__(
        self,
        active_assets_service: Any = None,
        parser_service: SFLogParserService | None = None,
        bridge_service: EvolutionBridgeService | None = None,
        compliance_gate: SFLogComplianceGate | None = None,
        cascade_service: CascadeService | None = None,
        registry_services: dict[str, Any] | None = None,  # 1C B2 新增
    ) -> None:
        self.active_assets_service = active_assets_service
        self.parser_service = parser_service
        self.bridge_service = bridge_service
        self.compliance_gate = compliance_gate
        self.cascade_service = cascade_service
        # 保留 None 语义：未配置 vs 已配置但为空 dict
        # - None → validate 跳过（DEGRADED）
        # - {} → 已配置但无服务（每个 asset_type 都被报 DEGRADED）
        self.registry_services = registry_services

    def load_active_assets_for_context(
        self,
        novel_id: str,
        chapter_id: int,
    ) -> ActiveAssetsContext:
        """Step 1 钩子：返回当前章节活跃资产摘要供 LLM context 使用。

        spec §4.1 Step 1：
            Runner->>Delegate: load_active_assets_for_context(novel_id, 5)
            Delegate-->>Runner: ActiveAssetsContext (4 conflicts, 2 mysteries, 1 expectation)
        """
        if self.active_assets_service is None:
            logger.debug("[storyos] active_assets_service 未注入，返回空 context")
            return ActiveAssetsContext(novel_id=novel_id, chapter_id=chapter_id)
        try:
            return self.active_assets_service.build_context(novel_id, chapter_id)
        except Exception as e:
            logger.warning(
                "[storyos] load_active_assets_for_context 失败，降级返回空 context: %s", e,
            )
            return ActiveAssetsContext(novel_id=novel_id, chapter_id=chapter_id)

    # 其他两个方法在 B2 / B3 任务中实现
    def validate_predeclared_changes(self, *args, **kwargs):  # placeholder
        raise NotImplementedError("Phase 1C Task B2")

    def apply_post_write_results(self, *args, **kwargs):  # placeholder
        raise NotImplementedError("Phase 1C Task B3")
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed

Run: `pytest tests/unit/engine/runtime/test_storyos_delegate.py::test_load_active_assets_for_context_delegates_to_service tests/unit/engine/runtime/test_storyos_delegate.py::test_load_active_assets_for_context_returns_empty_on_service_none tests/unit/engine/runtime/test_storyos_delegate.py::test_load_active_assets_for_context_returns_empty_on_service_failure -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add engine/runtime/storyos_delegate.py tests/unit/engine/runtime/test_storyos_delegate.py
git commit -m "feat(engine): add StoryOSDelegate.load_active_assets_for_context (spec §2.3 Step 1)"
```

---

#### Task B2: validate_predeclared_changes

**Files:**
- Modify: `engine/runtime/storyos_delegate.py`（追加方法）
- Create: `tests/unit/engine/runtime/test_storyos_delegate.py`（追加测试）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/engine/runtime/test_storyos_delegate.py（追加）

from domain.storyos.value_objects.predeclared import (
    PredeclaredChange, PredeclaredChanges,
)
from domain.storyos.contracts import SFLogType


def test_validate_predeclared_changes_returns_valid_when_all_assets_exist():
    """Step 3 钩子: 所有 predeclared asset_id 在 registry 中存在时 valid=True

    设计：B2 通过 registry_services.get(asset_type).get(asset_id) 检查存在性
    （1B GenericRegistryService.get 抛 KeyError 表示不存在）。
    cascade_service 用于额外的 cascade 深度/循环校验。
    """
    mystery_svc = MagicMock()
    mystery_svc.get.return_value = MagicMock(id="m1")  # 存在

    delegate = StoryOSDelegate(registry_services={"mystery": mystery_svc})
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery", asset_id="m1",
        ),
    ])
    result = delegate.validate_predeclared_changes("n1", 5, predeclared)
    assert result.valid is True
    assert result.issues == []
    mystery_svc.get.assert_called_once_with("m1")


def test_validate_predeclared_changes_returns_invalid_when_asset_not_found():
    """Step 3 钩子: asset_id 在 registry 中不存在时 valid=False（orphan）"""
    from application.storyos.services.predeclared_validation import PredeclaredIssueType

    mystery_svc = MagicMock()
    mystery_svc.get.side_effect = KeyError("m1")

    delegate = StoryOSDelegate(registry_services={"mystery": mystery_svc})
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery", asset_id="m1",
        ),
    ])
    result = delegate.validate_predeclared_changes("n1", 5, predeclared)
    assert result.valid is False
    assert len(result.issues) == 1
    assert result.issues[0].type == PredeclaredIssueType.ORPHAN_ASSET
    assert result.issues[0].asset_id == "m1"


def test_validate_predeclared_changes_handles_asset_pair():
    """Step 3 钩子: asset_pair 形式（CHARACTER_RELATION_CHANGE）的 predeclared
    需要检查两个 asset 都存在。

    1A PredeclaredChange XOR: 只能有 asset_id 或 asset_pair 之一。
    1B LOG_TYPE_TO_PAIR_TYPES 映射处理 character relation 类型。
    """
    character_svc = MagicMock()
    character_svc.get.return_value = MagicMock(id="c1")

    delegate = StoryOSDelegate(registry_services={"character": character_svc})
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.CHARACTER_RELATION_CHANGE,
            asset_type="character",
            asset_pair=("c1", "c2"),  # 两个角色
        ),
    ])
    result = delegate.validate_predeclared_changes("n1", 5, predeclared)
    # c1 存在，c2 缺失 → valid=False
    assert result.valid is False
    assert any(i.asset_id == "c2" for i in result.issues)
    # c1.get 调一次，c2.get 调一次（mock 默认未配置 → KeyError）
    assert character_svc.get.call_count == 2


def test_validate_predeclared_changes_returns_valid_when_registries_none():
    """降级: registry_services 未注入时返回 valid=True + issues 记录降级原因"""
    delegate = StoryOSDelegate(registry_services=None)
    predeclared = PredeclaredChanges()
    result = delegate.validate_predeclared_changes("n1", 5, predeclared)
    assert result.valid is True
    assert any("registry_services 未注入" in issue.message for issue in result.issues)


def test_validate_predeclared_changes_returns_valid_when_asset_type_not_in_registries():
    """降级: predeclared 的 asset_type 不在 registry_services 中时（未配置）跳过检查"""
    delegate = StoryOSDelegate(registry_services={})  # 空 dict
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery", asset_id="m1",
        ),
    ])
    result = delegate.validate_predeclared_changes("n1", 5, predeclared)
    # mystery registry 未配置 → valid=True（不阻断）
    assert result.valid is True
    assert any("mystery" in issue.message for issue in result.issues)
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `NotImplementedError`

Run: `pytest tests/unit/engine/runtime/test_storyos_delegate.py -v -k "validate_predeclared"`
Expected: FAILED with `NotImplementedError: Phase 1C Task B2`

- [ ] **Step 3: 实现** — 修改 `engine/runtime/storyos_delegate.py`，添加：

```python
# engine/runtime/storyos_delegate.py（追加方法到 StoryOSDelegate 类）

    def validate_predeclared_changes(
        self,
        novel_id: str,
        chapter_id: int,
        predeclared: PredeclaredChanges,
    ) -> Any:  # PredeclaredValidation 在 1C 创建
        """Step 3 钩子：校验 predeclared_changes 引用的 asset 是否存在。

        spec §4.1 Step 3：
            Runner->>Delegate: validate_predeclared_changes(novel_id, 5, predeclared)
            Delegate-->>Runner: PredeclaredValidation(valid=True)

        实现（spec §4.3 B + 1B GenericRegistryService 锁定）：
        1. 对每个 PredeclaredChange，按 asset_type 查 registry_services[asset_type]
        2. asset_id 存在 → OK；不存在（KeyError）→ ORPHAN_ASSET issue
        3. asset_pair 形式 → 两个 asset_id 都查，任一缺失 → ORPHAN_ASSET
        4. cascade_service 是可选的额外校验（深度/循环），不在 1C 必填范围

        降级（spec §4.3 F）：
        - registry_services 未注入 → valid=True + DEGRADED issue
        - asset_type 不在 registry_services 中 → valid=True + DEGRADED issue
        - registry.get 抛非 KeyError 异常 → 降级 valid=True + DEGRADED issue
        """
        # 避免循环 import
        from application.storyos.services.predeclared_validation import (
            PredeclaredValidation, PredeclaredIssue, PredeclaredIssueType,
        )

        if self.registry_services is None:
            logger.debug("[storyos] registry_services 未注入，validate 跳过")
            return PredeclaredValidation(
                valid=True,
                issues=[
                    PredeclaredIssue(
                        type=PredeclaredIssueType.DEGRADED,
                        message="registry_services 未注入，跳过 asset 存在性校验",
                    ),
                ],
            )

        issues = []
        try:
            for p in predeclared:
                svc = self.registry_services.get(p.asset_type)
                if svc is None:
                    # asset_type 不在配置中 → 跳过（不阻断）
                    issues.append(PredeclaredIssue(
                        type=PredeclaredIssueType.DEGRADED,
                        asset_id=p.asset_id,
                        message=f"asset_type {p.asset_type!r} 无对应 registry，跳过校验",
                    ))
                    continue

                # 1A PredeclaredChange XOR: asset_id XOR asset_pair
                asset_ids_to_check = []
                if p.asset_id is not None:
                    asset_ids_to_check.append(p.asset_id)
                if p.asset_pair is not None:
                    asset_ids_to_check.extend(p.asset_pair)

                for aid in asset_ids_to_check:
                    try:
                        svc.get(aid)
                    except KeyError:
                        issues.append(PredeclaredIssue(
                            type=PredeclaredIssueType.ORPHAN_ASSET,
                            asset_id=aid,
                            message=f"asset {aid!r} not found in {p.asset_type} registry",
                        ))
                    except Exception as e:
                        logger.warning(
                            "[storyos] registry_services[%r].get(%r) 失败: %s",
                            p.asset_type, aid, e,
                        )
                        issues.append(PredeclaredIssue(
                            type=PredeclaredIssueType.DEGRADED,
                            asset_id=aid,
                            message=f"registry 异常: {e}",
                        ))

        except Exception as e:
            logger.warning(
                "[storyos] validate_predeclared_changes 失败，降级 valid=True: %s", e,
            )
            return PredeclaredValidation(
                valid=True,
                issues=[
                    PredeclaredIssue(
                        type=PredeclaredIssueType.DEGRADED,
                        message=f"validate_predeclared_changes 异常: {e}",
                    ),
                ],
            )

        # 过滤掉 DEGRADED 后判断 valid（DEGRADED 不阻断，只记录）
        blocking_issues = [
            i for i in issues
            if i.type != PredeclaredIssueType.DEGRADED
        ]
        return PredeclaredValidation(
            valid=len(blocking_issues) == 0,
            issues=issues,
        )
```

**注**：本任务实施时若 `PredeclaredValidation` / `PredeclaredIssue` / `PredeclaredIssueType` 1B 阶段尚未定义，使用以下最小占位（在 `application/storyos/services/predeclared_validation.py` 临时创建，1B 已实施则忽略）：

```python
# application/storyos/services/predeclared_validation.py（如 1B 缺失则补）
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PredeclaredIssueType(str, Enum):
    ORPHAN_ASSET = "orphan_asset"
    BLOCKED_STEP = "blocked_step"
    TYPE_MISMATCH = "type_mismatch"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class PredeclaredIssue:
    type: PredeclaredIssueType
    message: str
    asset_id: str | None = None


@dataclass(frozen=True)
class PredeclaredValidation:
    valid: bool
    issues: list[PredeclaredIssue] = field(default_factory=list)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed（4 个核心 + 1 个 asset_pair）

Run: `pytest tests/unit/engine/runtime/test_storyos_delegate.py -v -k "validate_predeclared"`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add engine/runtime/storyos_delegate.py application/storyos/services/predeclared_validation.py tests/unit/engine/runtime/test_storyos_delegate.py
git commit -m "feat(engine): add StoryOSDelegate.validate_predeclared_changes (spec §2.3 Step 3)"
```

---

#### Task B3: apply_post_write_results

**Files:**
- Modify: `engine/runtime/storyos_delegate.py`（追加方法）
- Create: `tests/unit/engine/runtime/test_storyos_delegate.py`（追加测试）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/engine/runtime/test_storyos_delegate.py（追加）

from application.storyos.value_objects.bridge_result import BridgeResult


def test_apply_post_write_results_happy_path():
    """Step 5-6 合并钩子: parse → validate → match → bridge 流水线"""
    parser = MagicMock()
    parser.parse.return_value = [MagicMock(log_type="mystery_clue", asset_id="m1")]
    parser.validate_format.return_value = []  # 无格式错误
    parser.match_against_predeclared.return_value = MagicMock(
        missing_changes=[],
        unexpected_records=[],
        should_retry=False,
    )

    bridge = MagicMock()
    # 1B BridgeResult 14 字段（spec §3.2 锁定）：bridge_id/chapter_id/transaction_id/...
    expected = BridgeResult(
        bridge_id="b1", chapter_id=5, transaction_id="tx1",
        success=True, evolution_actions_applied=3, sflog_events_recorded=1,
    )
    bridge.apply_sflog_batch.return_value = expected

    delegate = StoryOSDelegate(parser_service=parser, bridge_service=bridge)
    predeclared = PredeclaredChanges()
    result = delegate.apply_post_write_results("n1", 5, "text", predeclared)

    assert result is expected
    assert result.success is True
    parser.parse.assert_called_once_with("text", 5)
    bridge.apply_sflog_batch.assert_called_once()


def test_apply_post_write_results_returns_failure_on_format_error():
    """Step 5: 格式错误时返回失败结果（不抛异常，spec §4.3 A）"""
    from domain.storyos.value_objects.format_error import FormatError

    parser = MagicMock()
    parser.parse.return_value = []
    parser.validate_format.return_value = [
        FormatError(code="MALFORMED_TAG", message="bad tag", char_position=10),
    ]

    delegate = StoryOSDelegate(parser_service=parser, bridge_service=MagicMock())
    result = delegate.apply_post_write_results("n1", 5, "text", PredeclaredChanges())
    assert result.success is False
    assert "MALFORMED_TAG" in (result.error or "")


def test_apply_post_write_results_bridge_failure_records_force_pass():
    """Step 6: bridge 失败时调用 compliance_gate.record_force_pass（spec §4.3 D）

    1B ComplianceGate 是通过 circuit_breaker 暴露 record_force_pass，
    delegate 必须走 circuit_breaker.record_force_pass(scope_id, gate, notes)
    """
    from application.storyos.services.evolution_bridge_service import EvolutionBridgeError

    parser = MagicMock()
    parser.parse.return_value = []
    parser.validate_format.return_value = []
    parser.match_against_predeclared.return_value = MagicMock(
        missing_changes=[], unexpected_records=[], should_retry=False,
    )

    bridge = MagicMock()
    bridge.apply_sflog_batch.side_effect = EvolutionBridgeError("SQL constraint")

    gate = MagicMock()
    # 1B SFLogComplianceGate 暴露 circuit_breaker 属性
    cb = MagicMock()
    gate.circuit_breaker = cb
    cb.record_force_pass = MagicMock()

    delegate = StoryOSDelegate(
        parser_service=parser, bridge_service=bridge, compliance_gate=gate,
    )
    result = delegate.apply_post_write_results("n1", 5, "text", PredeclaredChanges())
    assert result.success is False
    cb.record_force_pass.assert_called_once()
    call_args = cb.record_force_pass.call_args
    # 1B record_force_pass(scope_id, gate, notes) 位置参数
    assert call_args.args[0] == "n1:5"  # scope_id
    assert call_args.args[1] == "evolution_bridge"  # gate name
    assert "SQL constraint" in call_args.args[2]  # notes


def test_apply_post_write_results_returns_failure_on_parser_exception():
    """降级: parser 抛异常时返回失败 BridgeResult（spec §4.3 F）

    返回的失败 BridgeResult 仍需 14 字段全填，success=False + error=...。
    """
    parser = MagicMock()
    parser.parse.side_effect = RuntimeError("regex catastrophic backtrack")
    delegate = StoryOSDelegate(parser_service=parser, bridge_service=MagicMock())
    result = delegate.apply_post_write_results("n1", 5, "text", PredeclaredChanges())
    assert result.success is False
    assert "regex catastrophic" in (result.error or "")
    # 验证 14 字段都有合法值（即使失败也保留结构）
    assert result.bridge_id  # 由 delegate 生成
    assert result.chapter_id == 5
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `NotImplementedError`

Run: `pytest tests/unit/engine/runtime/test_storyos_delegate.py -v -k "apply_post_write"`
Expected: FAILED with `NotImplementedError: Phase 1C Task B3`

- [ ] **Step 3: 实现** — 修改 `engine/runtime/storyos_delegate.py`，添加：

```python
# engine/runtime/storyos_delegate.py（追加方法到 StoryOSDelegate 类）

    def apply_post_write_results(
        self,
        novel_id: str,
        chapter_id: int,
        text: str,
        predeclared: PredeclaredChanges,
    ) -> BridgeResult:
        """Step 5-6 合并钩子：parse → validate → match → bridge。

        spec §4.1 Step 5：
            Runner->>Parser: parse(text, chapter_id=5)
            Runner->>Parser: validate_format(text)
            Runner->>Parser: match_against_predeclared(records, predeclared)
        spec §4.1 Step 6：
            Runner->>Bridge: apply_sflog_batch(novel_id, 5, records)

        失败模式（spec §4.3）：
        - A 格式错误 → 返回 success=False BridgeResult（14 字段，error 含 format code）
        - B predeclared 校验失败 → 调 compliance_gate.evaluate 走 RETRY/FORCE_PASS
        - C cascade 错误 → bridge 内部处理
        - D bridge 错误 → ROLLBACK + 调 circuit_breaker.record_force_pass
        - F 持久化错误 → bridge 内部 retry

        BridgeResult 字段（1B spec §3.2 锁定 14 字段）：
            bridge_id, chapter_id, transaction_id,
            evolution_actions_applied, evolution_actions_skipped, skipped_log_types,
            registry_updates_applied, cascade_steps_executed, cascade_steps_blocked,
            sflog_events_recorded, success, warnings, duration_ms, error
        """
        scope_id = f"{novel_id}:{chapter_id}"
        if self.parser_service is None or self.bridge_service is None:
            logger.warning("[storyos] parser_service/bridge_service 未注入")
            return BridgeResult(
                bridge_id=f"degraded-{scope_id}", chapter_id=chapter_id,
                transaction_id=None, success=False,
                error="parser_service or bridge_service not configured",
            )

        try:
            records = self.parser_service.parse(text, chapter_id)
        except Exception as e:
            logger.warning("[storyos] parser.parse 失败: %s", e)
            return BridgeResult(
                bridge_id=f"degraded-{scope_id}", chapter_id=chapter_id,
                transaction_id=None, success=False,
                error=f"parser.parse 异常: {e}",
            )

        try:
            format_errors = self.parser_service.validate_format(records)
        except Exception as e:
            logger.warning("[storyos] parser.validate_format 失败: %s", e)
            format_errors = []

        if format_errors:
            # spec §4.3 A: 格式错误不阻断 pipeline，记录 status='format_error'
            return BridgeResult(
                bridge_id=f"format-error-{scope_id}", chapter_id=chapter_id,
                transaction_id=None, success=False,
                warnings=[f"format_error: {e.code}" for e in format_errors],
                error=f"format errors: {[e.code for e in format_errors]}",
            )

        try:
            match_report = self.parser_service.match_against_predeclared(records, predeclared)
        except Exception as e:
            logger.warning("[storyos] match_against_predeclared 失败: %s", e)
            match_report = None

        # spec §4.4：missing_changes 触发 RETRY → 阈值后 FORCE_PASS
        # 1B SFLogComplianceGate.evaluate(predeclared, records, scope_id) 签名
        if self.compliance_gate is not None and match_report is not None:
            try:
                decision = self.compliance_gate.evaluate(predeclared, records, scope_id)
                if decision == ComplianceDecision.RETRY:
                    logger.info(
                        "[storyos] match_report missing=%d，RETRY 决策由 PipelineRunner 处理",
                        len(match_report.missing_changes),
                    )
                # FORCE_PASS / PASS / WARN 都不阻断，继续走 bridge
            except Exception as e:
                logger.warning("[storyos] compliance_gate.evaluate 失败: %s", e)

        try:
            return self.bridge_service.apply_sflog_batch(novel_id, chapter_id, records)
        except EvolutionBridgeError as e:
            # spec §4.3 D: bridge 错误 ROLLBACK + force_pass
            logger.warning("[storyos] bridge 失败: %s", e)
            if self.compliance_gate is not None and self.compliance_gate.circuit_breaker is not None:
                try:
                    # 1B record_force_pass(scope_id, gate, notes) 位置参数
                    self.compliance_gate.circuit_breaker.record_force_pass(
                        scope_id, "evolution_bridge", f"bridge failed: {e}",
                    )
                except Exception as gate_err:
                    logger.warning("[storyos] record_force_pass 失败: %s", gate_err)
            return BridgeResult(
                bridge_id=f"bridge-failed-{scope_id}", chapter_id=chapter_id,
                transaction_id=None, success=False,
                error=f"bridge failed: {e}",
            )
        except Exception as e:
            # spec §4.3 F: 未知错误
            logger.error("[storyos] apply_post_write_results 未知错误: %s", e, exc_info=True)
            return BridgeResult(
                bridge_id=f"unknown-error-{scope_id}", chapter_id=chapter_id,
                transaction_id=None, success=False,
                error=f"unknown error: {e}",
            )
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed

Run: `pytest tests/unit/engine/runtime/test_storyos_delegate.py -v -k "apply_post_write"`
Expected: 4 passed

- [ ] **Step 5: 运行所有 delegate 测试确认整体通过** — 期望 12 passed

Run: `pytest tests/unit/engine/runtime/test_storyos_delegate.py -v`
Expected: 12 passed（3 B1 load + 5 B2 validate + 4 B3 apply）

- [ ] **Step 6: Commit**

```bash
git add engine/runtime/storyos_delegate.py tests/unit/engine/runtime/test_storyos_delegate.py
git commit -m "feat(engine): add StoryOSDelegate.apply_post_write_results (spec §2.3 Step 5-6)"
```

---

### Group C: 4 钩子接入

#### Task C1: PipelineRunner 在 4 个步骤调用 delegate + 降级处理

**Files:**
- Modify: `engine/pipeline/base.py:332-434`（`_step_build_context` 末尾追加 Step 1 钩子）
- Modify: `engine/pipeline/base.py:436-489`（`_step_prepare_chapter_plan` 末尾追加 Step 3 钩子）
- Modify: `engine/pipeline/base.py:612-674`（`_step_validate_content` 末尾追加 Step 5 钩子）
- Modify: `engine/pipeline/base.py:675-720`（`_step_save_chapter` 与 `_step_run_post_commit` 之间追加 Step 6 钩子）
- Create: `tests/dag/storyos/test_hook_step1_context_load.py`
- Create: `tests/dag/storyos/test_hook_step3_pre_write_gate.py`
- Create: `tests/dag/storyos/test_hook_step5_post_write_gate.py`
- Create: `tests/dag/storyos/test_hook_step6_apply_state.py`
- Create: `tests/dag/storyos/test_pipeline_degraded_when_delegate_fails.py`

- [ ] **Step 1: PipelineContext 新增 4 个字段（storyos_active_assets / storyos_validation / storyos_bridge_result / storyos_failed）**

修改 `engine/pipeline/context.py`，在 `scene_plan` 字段后新增：

```python
# engine/pipeline/context.py（修改 line 65 之后）

    # ═══ StoryOS 集成产出（1C spec §2.3）═══
    scene_plan: Optional[ScenePlan] = None       # 章节执行剧本（spec §3.1）
    storyos_active_assets: Optional[ActiveAssetsContext] = None  # Step 1 产出
    storyos_validation: Optional[Any] = None     # Step 3 产出（PredeclaredValidation）
    storyos_bridge_result: Optional[Any] = None  # Step 6 产出（BridgeResult）
    storyos_failed: List[str] = field(default_factory=list)  # 降级记录（spec §4.3 F）
```

并在文件顶部 import：

```python
# engine/pipeline/context.py（顶部 import 区）
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext
```

- [ ] **Step 2: 写失败测试（Step 1 钩子集成测试）**

```python
# tests/dag/storyos/test_hook_step1_context_load.py
import pytest
from unittest.mock import MagicMock, patch
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext


class TestStep1Hook:
    def test_build_context_calls_load_active_assets(self):
        """Step 1: _step_build_context 调用 delegate.load_active_assets_for_context"""
        delegate = MagicMock(spec=StoryOSDelegate)
        expected = ActiveAssetsContext(
            novel_id="n1", chapter_id=5,
            conflicts=[{"id": "c1"}], mysteries=[{"id": "m1"}],
        )
        delegate.load_active_assets_for_context.return_value = expected

        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        ctx.storyos_delegate = delegate

        # 模拟 _step_build_context 的关键路径
        # （完整 10 步需要 chapter_workflow 等依赖；这里只测 hook 本身）
        from engine.pipeline.steps import StepResult
        # 直接调内部 hook 入口
        result = pipeline._hook_step1_context_load(ctx)
        assert result is expected
        assert ctx.storyos_active_assets is expected
        delegate.load_active_assets_for_context.assert_called_once_with("n1", 5)

    def test_step1_hook_degrades_on_delegate_failure(self):
        """Step 1 降级: delegate 抛异常时记录到 ctx.storyos_failed，不抛异常"""
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.load_active_assets_for_context.side_effect = RuntimeError("boom")

        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        ctx.storyos_delegate = delegate

        result = pipeline._hook_step1_context_load(ctx)
        assert result is None
        assert "step1_context_load" in ctx.storyos_failed
```

- [ ] **Step 3: 运行测试确认失败** — 期望 `AttributeError: 'BaseStoryPipeline' object has no attribute '_hook_step1_context_load'`

Run: `pytest tests/dag/storyos/test_hook_step1_context_load.py -v`
Expected: FAILED with `AttributeError`

- [ ] **Step 4: 实现 4 个 hook 入口** — 修改 `engine/pipeline/base.py`，在 `_step_log` 方法之后（约 line 1222）添加：

```python
# engine/pipeline/base.py（新增 hook 入口，4 个方法）

    def _get_storyos_delegate(self, ctx: PipelineContext) -> Any:
        """从 ctx.metadata 或 ctx._dependencies 获取 StoryOSDelegate（spec §2.3）"""
        return getattr(ctx, "storyos_delegate", None) or ctx.get_dep("storyos_delegate")

    def _hook_step1_context_load(self, ctx: PipelineContext) -> Any:
        """Step 1 钩子：context-load → delegate.load_active_assets_for_context

        spec §4.1 Step 1。降级：失败时记录到 ctx.storyos_failed，返回 None。
        """
        delegate = self._get_storyos_delegate(ctx)
        if delegate is None:
            ctx.storyos_failed.append("step1_context_load: delegate not configured")
            return None
        try:
            result = delegate.load_active_assets_for_context(
                ctx.novel_id, int(ctx.chapter_number),
            )
            ctx.storyos_active_assets = result
            return result
        except Exception as e:
            logger.warning("[%s] Step 1 hook 失败: %s", ctx.novel_id, e)
            ctx.storyos_failed.append(f"step1_context_load: {e}")
            return None

    def _hook_step3_pre_write_gate(
        self, ctx: PipelineContext, predeclared: Any,
    ) -> Any:
        """Step 3 钩子：pre-write gate → delegate.validate_predeclared_changes

        spec §4.1 Step 3。降级：失败时 valid=True（不阻断 pipeline）。
        """
        delegate = self._get_storyos_delegate(ctx)
        if delegate is None:
            ctx.storyos_failed.append("step3_pre_write_gate: delegate not configured")
            return None
        try:
            result = delegate.validate_predeclared_changes(
                ctx.novel_id, int(ctx.chapter_number), predeclared,
            )
            ctx.storyos_validation = result
            return result
        except Exception as e:
            logger.warning("[%s] Step 3 hook 失败: %s", ctx.novel_id, e)
            ctx.storyos_failed.append(f"step3_pre_write_gate: {e}")
            return None

    def _hook_step5_post_write_gate(
        self, ctx: PipelineContext, text: str, predeclared: Any,
    ) -> Any:
        """Step 5 钩子：post-write gate → parser.parse + validate + match

        spec §4.1 Step 5。这是 apply_post_write_results 的前半段，单独调用用于
        在 save_chapter 之前做 match 决策（两级重试）。Step 6 仍会调
        apply_post_write_results 走完整流水线。
        """
        delegate = self._get_storyos_delegate(ctx)
        if delegate is None:
            ctx.storyos_failed.append("step5_post_write_gate: delegate not configured")
            return None
        # Step 5 只做 match 决策，不实际写库
        if not hasattr(delegate, "parser_service") or delegate.parser_service is None:
            ctx.storyos_failed.append("step5_post_write_gate: parser_service not configured")
            return None
        try:
            records = delegate.parser_service.parse(text, int(ctx.chapter_number))
            format_errors = delegate.parser_service.validate_format(records)
            if format_errors:
                ctx.storyos_failed.append(
                    f"step5_post_write_gate: format errors {[e.code for e in format_errors]}"
                )
                return {"format_errors": format_errors, "records": records}
            match_report = delegate.parser_service.match_against_predeclared(records, predeclared)
            return {
                "format_errors": [],
                "records": records,
                "match_report": match_report,
            }
        except Exception as e:
            logger.warning("[%s] Step 5 hook 失败: %s", ctx.novel_id, e)
            ctx.storyos_failed.append(f"step5_post_write_gate: {e}")
            return None

    def _hook_step6_apply_state(
        self, ctx: PipelineContext, text: str, predeclared: Any,
    ) -> Any:
        """Step 6 钩子：apply-state → delegate.apply_post_write_results

        spec §4.1 Step 6。降级：失败时记录到 ctx.storyos_failed，不抛异常。
        """
        delegate = self._get_storyos_delegate(ctx)
        if delegate is None:
            ctx.storyos_failed.append("step6_apply_state: delegate not configured")
            return None
        try:
            result = delegate.apply_post_write_results(
                ctx.novel_id, int(ctx.chapter_number), text, predeclared,
            )
            ctx.storyos_bridge_result = result
            return result
        except Exception as e:
            logger.warning("[%s] Step 6 hook 失败: %s", ctx.novel_id, e)
            ctx.storyos_failed.append(f"step6_apply_state: {e}")
            return None
```

- [ ] **Step 5: 修改 4 个 _step_* 方法调用 hook**

**`_step_build_context` 末尾追加（line 434 之前）**：

```python
# engine/pipeline/base.py（修改 _step_build_context）

        # ─── StoryOS Step 1 钩子：注入活跃资产摘要（spec §2.3）───
        if ctx.get_dep("storyos_delegate") is not None or hasattr(ctx, "storyos_delegate"):
            try:
                active = self._hook_step1_context_load(ctx)
                if active is not None:
                    # 注入到 context_text（自然语言摘要）
                    asset_summary = self._format_active_assets_for_prompt(active)
                    if asset_summary:
                        ctx.context_text = (ctx.context_text or "") + "\n\n" + asset_summary
                        logger.info(
                            "[%s] 注入 %d 个活跃资产到上下文",
                            ctx.novel_id, active.total_active,
                        )
            except Exception as e:
                logger.warning("[%s] Step 1 钩子注入失败: %s", ctx.novel_id, e)

        return StepResult.ok()
```

并在 `BaseStoryPipeline` 中添加 `_format_active_assets_for_prompt` 辅助方法：

```python
# engine/pipeline/base.py（新增辅助方法）

    def _format_active_assets_for_prompt(self, active: Any) -> str:
        """把 ActiveAssetsContext 格式化为 prompt 友好的文本块。"""
        if active is None or active.total_active == 0:
            return ""
        lines = ["=== 本章活跃资产 ==="]
        for field in ["conflicts", "mysteries", "twists", "promises", "reveals",
                      "expectations", "goals", "foreshadowings"]:
            items = getattr(active, field, [])
            if items:
                lines.append(f"\n【{field}】（{len(items)} 项）")
                for item in items[:3]:  # 限 3 个避免 prompt 膨胀
                    asset_id = item.get("id", "?") if isinstance(item, dict) else "?"
                    desc = item.get("description", "") if isinstance(item, dict) else ""
                    lines.append(f"- {asset_id}: {desc[:60]}")
        return "\n".join(lines)
```

**`_step_prepare_chapter_plan` 末尾追加（line 488 之后，`return StepResult.ok()` 之前）**：

```python
# engine/pipeline/base.py（修改 _step_prepare_chapter_plan）

        # ─── StoryOS Step 3 钩子：pre-write gate 校验 predeclared（spec §2.3）───
        if ctx.scene_plan is not None and ctx.scene_plan.predeclared_changes:
            validation = self._hook_step3_pre_write_gate(
                ctx, ctx.scene_plan.predeclared_changes,
            )
            if validation is not None and not getattr(validation, "valid", True):
                logger.warning(
                    "[%s] Step 3 predeclared 校验发现问题: %s",
                    ctx.novel_id,
                    [i.message for i in getattr(validation, "issues", [])],
                )
                # 校验失败不阻断，但记录到 metadata 供 1D 前端展示
                ctx.metadata["storyos_predeclared_issues"] = [
                    {"type": i.type.value, "message": i.message, "asset_id": i.asset_id}
                    for i in validation.issues
                ]
```

**`_step_validate_content` 末尾追加（line 673 之前，`return StepResult.ok()` 之前）**：

```python
# engine/pipeline/base.py（修改 _step_validate_content）

        # ─── StoryOS Step 5 钩子：post-write gate 解析 SF_LOG + match（spec §2.3）───
        if ctx.chapter_content and ctx.scene_plan is not None:
            match_result = self._hook_step5_post_write_gate(
                ctx, ctx.chapter_content, ctx.scene_plan.predeclared_changes,
            )
            if match_result and "match_report" in match_result:
                match_report = match_result["match_report"]
                ctx.metadata["storyos_match_rate"] = match_report.match_rate
                ctx.metadata["storyos_missing_changes"] = [
                    {"log_type": p.log_type.value, "asset_id": p.asset_id}
                    for p in match_report.missing_changes
                ]
                if match_report.should_retry:
                    logger.warning(
                        "[%s] Step 5 match: %d 个 predeclared 未实现（不阻断，由 Step 6 决策）",
                        ctx.novel_id, len(match_report.missing_changes),
                    )

        return StepResult.ok()
```

**`_step_save_chapter` 与 `_step_run_post_commit` 之间追加**：

修改 `engine/pipeline/base.py:170-173`（`save_chapter` 步骤结束后），在 `self._mark_pipeline_step(ctx, "save_chapter", completed=True)` 之后立即插入：

```python
# engine/pipeline/base.py（修改 run_chapter 在 save_chapter 步骤完成后）

            self._mark_pipeline_step(ctx, "save_chapter", completed=True)

            # ─── StoryOS Step 6 钩子：apply-state 走 WriteDispatch 单事务（spec §2.3）───
            if ctx.chapter_content and ctx.scene_plan is not None:
                bridge_result = self._hook_step6_apply_state(
                    ctx, ctx.chapter_content, ctx.scene_plan.predeclared_changes,
                )
                if bridge_result is not None:
                    # 1B BridgeResult 字段（spec §3.2 锁定）：
                    #   success / cascade_steps_executed / cascade_steps_blocked /
                    #   evolution_actions_applied / sflog_events_recorded / error / warnings
                    ctx.metadata["storyos_bridge_success"] = bridge_result.success
                    ctx.metadata["storyos_cascade_count"] = int(
                        getattr(bridge_result, "cascade_steps_executed", 0) or 0
                    )
                    ctx.metadata["storyos_cascade_blocked"] = len(
                        getattr(bridge_result, "cascade_steps_blocked", []) or []
                    )
                    ctx.metadata["storyos_evolution_actions"] = int(
                        getattr(bridge_result, "evolution_actions_applied", 0) or 0
                    )
                    if not bridge_result.success:
                        logger.warning(
                            "[%s] Step 6 bridge 失败: %s",
                            ctx.novel_id, getattr(bridge_result, "error", ""),
                        )

            # 7. 文风审计
            ...
```

- [ ] **Step 6: 运行 Step 1 钩子测试** — 期望 2 passed

Run: `pytest tests/dag/storyos/test_hook_step1_context_load.py -v`
Expected: 2 passed

- [ ] **Step 7: 写并运行 Step 3 钩子测试**

```python
# tests/dag/storyos/test_hook_step3_pre_write_gate.py
import pytest
from unittest.mock import MagicMock
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate
from domain.storyos.value_objects.predeclared import PredeclaredChanges
from application.storyos.services.predeclared_validation import (
    PredeclaredValidation, PredeclaredIssue, PredeclaredIssueType,
)


class TestStep3Hook:
    def test_validate_predeclared_calls_delegate(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        expected = PredeclaredValidation(valid=True, issues=[])
        delegate.validate_predeclared_changes.return_value = expected
        ctx.storyos_delegate = delegate
        predeclared = PredeclaredChanges()

        result = pipeline._hook_step3_pre_write_gate(ctx, predeclared)
        assert result is expected
        assert ctx.storyos_validation is expected
        delegate.validate_predeclared_changes.assert_called_once_with("n1", 5, predeclared)

    def test_step3_hook_degrades_on_delegate_failure(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.validate_predeclared_changes.side_effect = RuntimeError("boom")
        ctx.storyos_delegate = delegate
        predeclared = PredeclaredChanges()

        result = pipeline._hook_step3_pre_write_gate(ctx, predeclared)
        assert result is None
        assert "step3_pre_write_gate" in ctx.storyos_failed
```

Run: `pytest tests/dag/storyos/test_hook_step3_pre_write_gate.py -v`
Expected: 2 passed

- [ ] **Step 8: 写并运行 Step 5 钩子测试**

```python
# tests/dag/storyos/test_hook_step5_post_write_gate.py
from unittest.mock import MagicMock
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate
from domain.storyos.value_objects.predeclared import PredeclaredChanges
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.predeclared import PredeclaredChange


class TestStep5Hook:
    def test_post_write_gate_returns_match_report(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)

        delegate = MagicMock(spec=StoryOSDelegate)
        parser = MagicMock()
        parser.parse.return_value = []
        parser.validate_format.return_value = []
        parser.match_against_predeclared.return_value = MagicMock(
            missing_changes=[], unexpected_records=[], should_retry=False,
        )
        delegate.parser_service = parser
        ctx.storyos_delegate = delegate

        predeclared = PredeclaredChanges(items=[
            PredeclaredChange(log_type=SFLogType.MYSTERY_CLUE, asset_type="mystery", asset_id="m1"),
        ])
        result = pipeline._hook_step5_post_write_gate(ctx, "text", predeclared)
        assert "match_report" in result
        assert "format_errors" in result
        assert result["format_errors"] == []

    def test_step5_hook_degrades_on_parser_failure(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.parser_service = MagicMock()
        delegate.parser_service.parse.side_effect = RuntimeError("boom")
        ctx.storyos_delegate = delegate

        result = pipeline._hook_step5_post_write_gate(ctx, "text", PredeclaredChanges())
        assert result is None
        assert "step5_post_write_gate" in ctx.storyos_failed
```

Run: `pytest tests/dag/storyos/test_hook_step5_post_write_gate.py -v`
Expected: 2 passed

- [ ] **Step 9: 写并运行 Step 6 钩子测试**

```python
# tests/dag/storyos/test_hook_step6_apply_state.py
from unittest.mock import MagicMock
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate
from domain.storyos.value_objects.predeclared import PredeclaredChanges
from application.storyos.value_objects.bridge_result import BridgeResult


class TestStep6Hook:
    def test_apply_state_calls_delegate(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        # 1B BridgeResult 14 字段
        expected = BridgeResult(
            bridge_id="b1", chapter_id=5, transaction_id="tx1",
            success=True, evolution_actions_applied=3, cascade_steps_executed=1,
            sflog_events_recorded=2,
        )
        delegate.apply_post_write_results.return_value = expected
        ctx.storyos_delegate = delegate
        predeclared = PredeclaredChanges()

        result = pipeline._hook_step6_apply_state(ctx, "text", predeclared)
        assert result is expected
        assert ctx.storyos_bridge_result is expected
        # metadata 暴露的应该是 cascade_steps_executed 计数（不是 steps 列表）
        assert ctx.metadata["storyos_cascade_count"] == 1
        delegate.apply_post_write_results.assert_called_once_with("n1", 5, "text", predeclared)

    def test_step6_hook_degrades_on_delegate_failure(self):
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.apply_post_write_results.side_effect = RuntimeError("boom")
        ctx.storyos_delegate = delegate

        result = pipeline._hook_step6_apply_state(ctx, "text", PredeclaredChanges())
        assert result is None
        assert "step6_apply_state" in ctx.storyos_failed
```

Run: `pytest tests/dag/storyos/test_hook_step6_apply_state.py -v`
Expected: 2 passed

- [ ] **Step 10: 写并运行降级测试**

```python
# tests/dag/storyos/test_pipeline_degraded_when_delegate_fails.py
from unittest.mock import MagicMock
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate


class TestPipelineDegraded:
    def test_all_4_hooks_degrade_gracefully(self):
        """spec §4.3 F: 4 个 hook 全部失败时 pipeline 仍能继续（不抛异常）"""
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.load_active_assets_for_context.side_effect = RuntimeError("step1")
        delegate.validate_predeclared_changes.side_effect = RuntimeError("step3")
        delegate.apply_post_write_results.side_effect = RuntimeError("step6")
        ctx.storyos_delegate = delegate

        from domain.storyos.value_objects.predeclared import PredeclaredChanges

        # 4 个 hook 全部调用
        pipeline._hook_step1_context_load(ctx)
        pipeline._hook_step3_pre_write_gate(ctx, PredeclaredChanges())
        pipeline._hook_step5_post_write_gate(ctx, "text", PredeclaredChanges())
        pipeline._hook_step6_apply_state(ctx, "text", PredeclaredChanges())

        # 全部降级到 failed 列表
        assert len(ctx.storyos_failed) == 4
        assert "step1_context_load" in " ".join(ctx.storyos_failed)
        assert "step3_pre_write_gate" in " ".join(ctx.storyos_failed)
        assert "step6_apply_state" in " ".join(ctx.storyos_failed)

    def test_no_delegate_does_not_crash(self):
        """spec §4.3 F: delegate 未注入时不抛异常（仅记录到 failed 列表）"""
        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        from domain.storyos.value_objects.predeclared import PredeclaredChanges

        pipeline._hook_step1_context_load(ctx)
        pipeline._hook_step3_pre_write_gate(ctx, PredeclaredChanges())
        pipeline._hook_step5_post_write_gate(ctx, "text", PredeclaredChanges())
        pipeline._hook_step6_apply_state(ctx, "text", PredeclaredChanges())

        assert len(ctx.storyos_failed) == 4
```

Run: `pytest tests/dag/storyos/test_pipeline_degraded_when_delegate_fails.py -v`
Expected: 2 passed

- [ ] **Step 11: 验证现有管线不破坏** — 运行所有 pipeline 测试

Run: `pytest tests/dag/ tests/unit/engine/ -v`
Expected: 全部通过（无回归）。若失败，**不要**降低测试要求去适配；先确认是否在 1A/1B 缺失的依赖上调用，必要时 mock 掉。

- [ ] **Step 12: Commit**

```bash
git add engine/pipeline/base.py engine/pipeline/context.py tests/dag/storyos/
git commit -m "feat(engine): integrate 4 StoryOS hooks into BaseStoryPipeline (spec §2.3)"
```

---

#### Task C2: DI 装配 — runner + daemon_host 注入 storyos_delegate

**Files:**
- Modify: `engine/runtime/runner.py:23-61`（`__init__` 新增 `storyos_delegate` 参数）
- Modify: `engine/runtime/runner.py:73-116`（`_make_context` 注入 delegate 到 ctx）
- Modify: `engine/runtime/daemon_host.py`（在 `init_daemon_dependencies` 中接受 `storyos_delegate` 参数）
- Create: `tests/unit/engine/runtime/test_runner_di.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/engine/runtime/test_runner_di.py
from unittest.mock import MagicMock
from engine.runtime.runner import StoryPipelineRunner
from engine.runtime.storyos_delegate import StoryOSDelegate


def test_runner_accepts_storyos_delegate_in_constructor():
    """runner.__init__ 接受 storyos_delegate 参数（spec §3.1）"""
    delegate = MagicMock(spec=StoryOSDelegate)
    runner = StoryPipelineRunner(storyos_delegate=delegate)
    assert runner.storyos_delegate is delegate


def test_runner_injects_delegate_into_context():
    """_make_context 把 storyos_delegate 注入 ctx（供 4 个 hook 读取）"""
    delegate = MagicMock(spec=StoryOSDelegate)
    runner = StoryPipelineRunner(storyos_delegate=delegate)

    ctx = runner._make_context("n1", 5)
    assert ctx.get_dep("storyos_delegate") is delegate
    # 验证 _step_* 流程能通过 _get_storyos_delegate 找到
    pipeline = StoryPipelineRunner()
    pipeline.storyos_delegate = delegate
    retrieved = pipeline._get_storyos_delegate(ctx)
    assert retrieved is delegate
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `TypeError: __init__() got an unexpected keyword argument 'storyos_delegate'`

Run: `pytest tests/unit/engine/runtime/test_runner_di.py -v`
Expected: FAILED with `TypeError`

- [ ] **Step 3: 修改 runner.py** — 在 `__init__` 添加参数：

```python
# engine/runtime/runner.py（修改 __init__ line 23-41）

    def __init__(
        self,
        novel_repository=None,
        llm_service=None,
        context_builder=None,
        background_task_service=None,
        planning_service=None,
        story_node_repo=None,
        chapter_repository=None,
        poll_interval: int = 5,
        voice_drift_service=None,
        circuit_breaker=None,
        chapter_workflow=None,
        aftermath_pipeline=None,
        volume_summary_service=None,
        foreshadowing_repository=None,
        knowledge_service=None,
        use_story_pipeline_for_writing: bool | None = None,
        storyos_delegate: StoryOSDelegate | None = None,  # 1C 新增
    ):
        BaseStoryPipeline.__init__(self)
        init_daemon_dependencies(
            self,
            novel_repository=novel_repository,
            llm_service=llm_service,
            context_builder=context_builder,
            background_task_service=background_task_service,
            planning_service=planning_service,
            story_node_repo=story_node_repo,
            chapter_repository=chapter_repository,
            poll_interval=poll_interval,
            voice_drift_service=voice_drift_service,
            circuit_breaker=circuit_breaker,
            chapter_workflow=chapter_workflow,
            aftermath_pipeline=aftermath_pipeline,
            volume_summary_service=volume_summary_service,
            foreshadowing_repository=foreshadowing_repository,
            knowledge_service=knowledge_service,
            use_story_pipeline_for_writing=use_story_pipeline_for_writing,
            storyos_delegate=storyos_delegate,  # 1C 新增
        )
        self._legacy_daemon: Any = None
```

并在顶部 import：

```python
# engine/runtime/runner.py（顶部 import 区）
from engine.runtime.storyos_delegate import StoryOSDelegate
```

修改 `_make_context` 注入到 ctx（line 73-116）：

```python
# engine/runtime/runner.py（修改 _make_context line 73-116）

    def _make_context(self, novel_id: str, chapter_number: int = 0, **kwargs) -> PipelineContext:
        ctx = PipelineContext(
            novel_id=novel_id,
            chapter_number=chapter_number,
            **kwargs,
        )
        ctx.inject(
            novel_repository=self.novel_repository,
            chapter_repository=self.chapter_repository,
            llm_service=self.llm_service,
            context_builder=self.context_builder,
            aftermath_pipeline=self.aftermath_pipeline,
            voice_drift_service=self.voice_drift_service,
            knowledge_service=self.knowledge_service,
            foreshadowing_repository=self.foreshadowing_repository,
            story_node_repo=self.story_node_repo,
            planning_service=self.planning_service,
            chapter_preplanning_service=getattr(self, "chapter_preplanning_service", None),
            chapter_workflow=self.chapter_workflow,
            background_task_service=self.background_task_service,
            circuit_breaker=self.circuit_breaker,
            volume_summary_service=self.volume_summary_service,
            autopilot_host=self.host,
            storyos_delegate=self.storyos_delegate,  # 1C 新增
        )
        # ... 其余不变
```

- [ ] **Step 4: 修改 daemon_host.py** — 修改 `init_daemon_dependencies` 函数（line ~XX，根据实际函数位置）：

```python
# engine/runtime/daemon_host.py（修改 init_daemon_dependencies 函数）

def init_daemon_dependencies(
    host,
    novel_repository=None,
    llm_service=None,
    context_builder=None,
    background_task_service=None,
    planning_service=None,
    story_node_repo=None,
    chapter_repository=None,
    poll_interval: int = 5,
    voice_drift_service=None,
    circuit_breaker=None,
    chapter_workflow=None,
    aftermath_pipeline=None,
    volume_summary_service=None,
    foreshadowing_repository=None,
    knowledge_service=None,
    use_story_pipeline_for_writing: bool | None = None,
    storyos_delegate: StoryOSDelegate | None = None,  # 1C 新增
):
    # ... 现有赋值逻辑
    host.storyos_delegate = storyos_delegate
    # 其余不变
```

- [ ] **Step 5: 运行 DI 测试** — 期望 2 passed

Run: `pytest tests/unit/engine/runtime/test_runner_di.py -v`
Expected: 2 passed

- [ ] **Step 6: 运行所有现有 engine 测试确认不破坏**

Run: `pytest tests/unit/engine/ tests/dag/ -v`
Expected: 全部通过

- [ ] **Step 7: Commit**

```bash
git add engine/runtime/runner.py engine/runtime/daemon_host.py tests/unit/engine/runtime/test_runner_di.py
git commit -m "feat(engine): inject StoryOSDelegate via runner/daemon_host DI (1C C2)"
```

---

### Group D: Prompt 注入点

#### Task D1: chapter-prose-generation/package.yaml 新增 sflog_directive

**Files:**
- Modify: `infrastructure/ai/prompt_packages/nodes/chapter-prose-generation/package.yaml:11-49`（variables 区追加 `sflog_directive`）
- Create: `infrastructure/ai/prompt_packages/nodes/chapter-prose-generation/sflog_directive.j2`（新增 Jinja2 模板）

- [ ] **Step 1: 验证文件存在性**

Run: `ls -la /Users/longsa/Codes/plotPilot/infrastructure/ai/prompt_packages/nodes/chapter-prose-generation/`
Expected: 至少包含 `package.yaml`

- [ ] **Step 2: 写失败测试**（验证 YAML 加载后能读到 sflog_directive 变量）

```python
# tests/integration/prompt_packages/test_chapter_prose_generation_sflog.py
from pathlib import Path
import yaml


def test_chapter_prose_generation_has_sflog_directive_variable():
    """spec §3.1: chapter-prose-generation/package.yaml 必须有 sflog_directive 变量"""
    pkg_path = Path(
        "/Users/longsa/Codes/plotPilot/infrastructure/ai/prompt_packages/"
        "nodes/chapter-prose-generation/package.yaml"
    )
    assert pkg_path.exists(), f"Missing: {pkg_path}"
    with open(pkg_path) as f:
        pkg = yaml.safe_load(f)
    variables = {v["name"] for v in pkg.get("variables", [])}
    assert "sflog_directive" in variables, (
        f"sflog_directive 变量缺失，现有变量: {variables}"
    )


def test_sflog_directive_j2_template_exists():
    """Jinja2 模板存在（spec §3.1 锁定 + 11 类 SF_LOG 示例）"""
    tpl_path = Path(
        "/Users/longsa/Codes/plotPilot/infrastructure/ai/prompt_packages/"
        "nodes/chapter-prose-generation/sflog_directive.j2"
    )
    assert tpl_path.exists(), f"Missing: {tpl_path}"
    content = tpl_path.read_text(encoding="utf-8")
    # 验证 11 类 SF_LOG 至少出现 6 类（spec §3.3 映射的 6 类）
    required_log_types = [
        "MYSTERY_CLUE", "CHARACTER_LOCATION_CHANGE", "CHARACTER_PHYSICAL_CHANGE",
        "CHARACTER_RELATION_CHANGE", "KNOWLEDGE_GAIN", "CONFLICT_ESCALATE",
    ]
    for log_type in required_log_types:
        assert log_type in content, f"{log_type} 示例缺失 in sflog_directive.j2"
```

- [ ] **Step 3: 运行测试确认失败** — 期望 `AssertionError: sflog_directive 变量缺失`

Run: `pytest tests/integration/prompt_packages/test_chapter_prose_generation_sflog.py -v`
Expected: FAILED with `AssertionError`

- [ ] **Step 4: 修改 package.yaml** — 在 variables 区末尾追加：

```yaml
# infrastructure/ai/prompt_packages/nodes/chapter-prose-generation/package.yaml（修改）

variables:
  # ... 现有 variables 保留 ...
  - name: sflog_directive
    desc: |
      StoryOS SF_LOG 指令块（spec §3.1 锁定 + 11 类 SF_LOG 提示）。
      由 engine/runtime/storyos_delegate.py 在 Step 1 注入 LLM 上下文。
      模板路径: sflog_directive.j2
    type: string
    default: ''
```

- [ ] **Step 5: 创建 sflog_directive.j2 模板** — 创建 `infrastructure/ai/prompt_packages/nodes/chapter-prose-generation/sflog_directive.j2`：

```jinja2
{# sflog_directive.j2 — StoryOS SF_LOG 指令块（spec §3.1 + §3.3）#}

=== StoryOS 状态变更标记（SF_LOG）===

本章如需在 narrative state 中留下资产操作标记，请使用以下 11 类 HTML 注释：

{# 6 类映射（spec §3.3 锁定，会被 evolution_bridge 实际处理） #}
- <!-- SF_LOG MYSTERY_CLUE mystery_id="<m>" content="<text>" -->         — 埋下/揭露线索
- <!-- SF_LOG CHARACTER_LOCATION_CHANGE char_id="<c>" location_id="<l>" -->  — 角色位置变化
- <!-- SF_LOG CHARACTER_PHYSICAL_CHANGE char_id="<c>" status="<status>" -->  — 角色状态变化（alive/dead/missing）
- <!-- SF_LOG CHARACTER_RELATION_CHANGE char_a="<c1>" char_b="<c2>" residue="<text>" -->  — 关系/情感残留
- <!-- SF_LOG KNOWLEDGE_GAIN char_id="<c>" fact="<text>" -->              — 角色获取知识
- <!-- SF_LOG CONFLICT_ESCALATE conflict_id="<c>" intensity_delta="<int>" -->  — 冲突升级

{# 5 类跳过（spec §3.3 锁定，仅记录到 sflog_event，不进入 evolution_bridge） #}
- <!-- SF_LOG CHARACTER_EMOTION char_id="<c>" emotion="<text>" -->        — 情感（仅记录）
- <!-- SF_LOG TWIST_REVEAL twist_id="<t>" type="<type>" -->              — 反转揭示
- <!-- SF_LOG EXPECTATION_FULFILL expectation_id="<e>" -->                — 预期兑现
- <!-- SF_LOG REGISTRY_CREATE asset_type="<type>" asset_id="<id>" name="<name>" -->  — 注册新资产
- <!-- SF_LOG GOAL_MILESTONE goal_id="<g>" progress="<int>" -->           — 目标里程碑

=== 预声明的资产操作（必须实现） ===
{{ predeclared_changes | default('（无）') }}

=== 写作规则 ===
1. 仅在确实改变了 narrative state 时插入 SF_LOG（不滥用）
2. SF_LOG 必须是合法 HTML 注释格式（<!-- ... -->），可被 regex_parser 提取
3. asset_id / char_id 等必须引用预声明或已注册资产
4. 若预声明中的某项资产未在本章实现，请在正文中明确说明或调整预声明（Step 3 validate_predeclared_changes 会检查）
```

- [ ] **Step 6: 运行测试确认通过** — 期望 2 passed

Run: `pytest tests/integration/prompt_packages/test_chapter_prose_generation_sflog.py -v`
Expected: 2 passed

- [ ] **Step 7: 验证 ProseComposer 消费 sflog_directive**

```python
# tests/integration/prompt_packages/test_prose_composer_includes_sflog.py
from pathlib import Path
import yaml


def test_prose_composer_sflog_directive_variable_default_is_j2_path():
    """ProseComposer 应知道从 ctx.metadata["sflog_directive"] 读取（spec §3.1 链路验证）"""
    # 由于 ProseComposer 不直接 import 这个 YAML，本测试仅验证 YAML 结构
    pkg_path = Path(
        "/Users/longsa/Codes/plotPilot/infrastructure/ai/prompt_packages/"
        "nodes/chapter-prose-generation/package.yaml"
    )
    with open(pkg_path) as f:
        pkg = yaml.safe_load(f)
    sflog_var = next(v for v in pkg["variables"] if v["name"] == "sflog_directive")
    assert sflog_var["type"] == "string"
    assert sflog_var["default"] == ""  # 由 1C 注入实际内容
```

Run: `pytest tests/integration/prompt_packages/test_prose_composer_includes_sflog.py -v`
Expected: 1 passed

- [ ] **Step 8: Commit**

```bash
git add infrastructure/ai/prompt_packages/nodes/chapter-prose-generation/ tests/integration/prompt_packages/
git commit -m "feat(prompt): add sflog_directive injection point to chapter-prose-generation (spec §3.1)"
```

---

## 4. 端到端集成测试（1C 阶段收尾）

**注意**：此任务在所有 8 个主任务完成后执行，作为 Phase 1C 完成的验收门。

#### Task E1: 端到端 happy path 集成测试

**Files:**
- Create: `tests/dag/storyos/test_end_to_end_happy_path.py`

- [ ] **Step 1: 写测试**（mock 整个 delegate，验证 4 个钩子在 BaseStoryPipeline 流程中被调用）

```python
# tests/dag/storyos/test_end_to_end_happy_path.py
"""spec §5.3: 端到端 happy path 验证 4 个钩子正确触发。"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from engine.pipeline.context import PipelineContext
from engine.pipeline.base import BaseStoryPipeline
from engine.runtime.storyos_delegate import StoryOSDelegate
from engine.pipeline.beat_contracts import ScenePlan
from domain.storyos.value_objects.predeclared import (
    PredeclaredChange, PredeclaredChanges,
)
from domain.storyos.contracts import SFLogType
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext
from application.storyos.value_objects.bridge_result import BridgeResult


class TestEndToEndHooks:
    def test_4_hooks_invoked_in_correct_order(self):
        """4 个 hook 按 spec §2.3 顺序触发：Step1 → Step3 → Step5 → Step6"""
        call_order = []
        delegate = MagicMock(spec=StoryOSDelegate)

        def step1_hook(novel_id, chapter_id):
            call_order.append("step1")
            return ActiveAssetsContext(novel_id=novel_id, chapter_id=chapter_id)
        delegate.load_active_assets_for_context.side_effect = step1_hook

        def step3_hook(novel_id, chapter_id, predeclared):
            call_order.append("step3")
            return MagicMock(valid=True, issues=[])
        delegate.validate_predeclared_changes.side_effect = step3_hook

        def step6_hook(novel_id, chapter_id, text, predeclared):
            call_order.append("step6")
            return BridgeResult(
                bridge_id="b1", chapter_id=chapter_id, transaction_id="tx1",
                success=True, evolution_actions_applied=3, sflog_events_recorded=1,
            )
        delegate.apply_post_write_results.side_effect = step6_hook

        delegate.parser_service = MagicMock()
        delegate.parser_service.parse.return_value = []
        delegate.parser_service.validate_format.return_value = []
        delegate.parser_service.match_against_predeclared.return_value = MagicMock(
            missing_changes=[], unexpected_records=[], should_retry=False,
        )

        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        ctx.storyos_delegate = delegate
        predeclared = PredeclaredChanges(items=[
            PredeclaredChange(log_type=SFLogType.MYSTERY_CLUE, asset_type="mystery", asset_id="m1"),
        ])
        ctx.scene_plan = ScenePlan(
            chapter_id=5, outline="outline", predeclared_changes=predeclared,
        )
        ctx.chapter_content = "正文 <!-- SF_LOG MYSTERY_CLUE mystery_id=\"m1\" content=\"blood\" --> 继续"

        # 手动触发 4 个 hook（完整 10 步需要更多依赖）
        pipeline._hook_step1_context_load(ctx)
        pipeline._hook_step3_pre_write_gate(ctx, predeclared)
        pipeline._hook_step5_post_write_gate(ctx, ctx.chapter_content, predeclared)
        pipeline._hook_step6_apply_state(ctx, ctx.chapter_content, predeclared)

        assert call_order == ["step1", "step3", "step6"]
        # Step 5 不在 call_order（它直接调 parser_service 不通过 delegate）
        # metadata 暴露的字段名（1B BridgeResult 14 字段）
        assert ctx.metadata["storyos_bridge_success"] is True
        assert ctx.metadata["storyos_evolution_actions"] == 3

    def test_no_warnings_on_clean_run(self):
        """clean run: storyos_failed 列表应为空"""
        delegate = MagicMock(spec=StoryOSDelegate)
        delegate.load_active_assets_for_context.return_value = ActiveAssetsContext(
            novel_id="n1", chapter_id=5,
        )
        delegate.validate_predeclared_changes.return_value = MagicMock(valid=True, issues=[])
        delegate.apply_post_write_results.return_value = BridgeResult(
            bridge_id="b1", chapter_id=5, transaction_id="tx1",
            success=True, evolution_actions_applied=3, cascade_steps_executed=1,
        )
        delegate.parser_service = MagicMock()
        delegate.parser_service.parse.return_value = []
        delegate.parser_service.validate_format.return_value = []
        delegate.parser_service.match_against_predeclared.return_value = MagicMock(
            missing_changes=[], unexpected_records=[], should_retry=False,
        )

        pipeline = BaseStoryPipeline()
        ctx = PipelineContext(novel_id="n1", chapter_number=5)
        ctx.storyos_delegate = delegate
        predeclared = PredeclaredChanges()
        ctx.scene_plan = ScenePlan(chapter_id=5, outline="", predeclared_changes=predeclared)

        pipeline._hook_step1_context_load(ctx)
        pipeline._hook_step3_pre_write_gate(ctx, predeclared)
        pipeline._hook_step5_post_write_gate(ctx, "text", predeclared)
        pipeline._hook_step6_apply_state(ctx, "text", predeclared)

        assert ctx.storyos_failed == []
        assert ctx.storyos_active_assets is not None
        assert ctx.storyos_validation is not None
        assert ctx.storyos_bridge_result is not None
```

- [ ] **Step 2: 运行端到端测试** — 期望 2 passed

Run: `pytest tests/dag/storyos/test_end_to_end_happy_path.py -v`
Expected: 2 passed

- [ ] **Step 3: 验证完整 DAG 测试套件** — 运行所有 DAG 测试

Run: `pytest tests/dag/storyos/ -v`
Expected: 全部通过（A1-A2 + B1-B3 + C1-C2 + D1 + E1 = 16+ 测试）

- [ ] **Step 4: Commit**

```bash
git add tests/dag/storyos/test_end_to_end_happy_path.py
git commit -m "test(engine): add end-to-end happy path for 4 StoryOS hooks (spec §5.3)"
```

---

## 5. 关键设计决策

### 5.1 钩子拆分（spec §2.3 6 步 vs spec §4.1 5 步）

spec §2.3 列出 6 步，spec §4.1 序列图把 Step 5（post-write gate）和 Step 6（apply-state）合并为一次 `delegate.apply_post_write_results` 调用。本计划**采用 §4.1 简化**：

- `apply_post_write_results` 内部编排 `parse → validate → match → bridge` 完整流水线
- 同时保留 `_hook_step5_post_write_gate` 单独入口供 PipelineRunner 在 save_chapter 之前做 match 决策（两级重试需要 match_report 信息）
- 这样既满足 spec §4.1 合并要求，又不丢失 spec §4.4 的 match_report 早期反馈能力

### 5.2 降级策略的边界

所有 4 个 hook 失败时**只**记录到 `ctx.storyos_failed` 列表，**不**抛异常。理由：
- spec §4.3 失败模式 F（Persistence Error）明确要求 WriteDispatch 自动重试
- StoryOS 是 optional augmentation，不是核心写作路径的一部分
- 若 StoryOS 全部关闭，pipeline 应与 1A 之前完全一致

`_step_finalize` 时把 `ctx.storyos_failed` 落到 `audit_snapshot["storyos_failures"]`，供 1D 前端展示。

### 5.3 ScenePlan 与 beats 的关系

`ScenePlan.beats` 与 `ctx.beats` 共享数据（同一份 beat list），但 `ScenePlan` 增加 `predeclared_changes` 字段。`serialize_beats_for_shared_state` 行为不变（向后兼容）。

`ScenePlan` 是 frozen dataclass，确保不可变；序列化通过 `to_shared_state_dict()` 方法。

### 5.4 sflog_directive 注入方式

`chapter-prose-generation/package.yaml` 声明 `sflog_directive` 变量（type=string, default=""），模板 `sflog_directive.j2` 在 1D 实施时由 ProseComposer 渲染。本任务（D1）只完成：
- YAML 变量声明（结构层）
- Jinja2 模板内容（spec §3.1 11 类 SF_LOG 提示）
- 测试验证两者协同

实际注入到 LLM 的链路（ctx.metadata["sflog_directive"] → ProseComposer → prompt 渲染）由 1D 实施连接。

### 5.5 predeclared validation 用 registry 查找而非 cascade.simulate

`validate_predeclared_changes` 通过 `registry_services: dict[str, GenericRegistryService]` 字典按 `asset_type` 查 `svc.get(asset_id)` 验证存在性（1B `KeyError` 语义）。**不**用 `cascade.simulate`，原因：

- `CascadeService.simulate` 检查 cascade 深度/循环，**不**检查 asset 存在性
- 自循环调用（`source_asset_id == target_asset_id`）会被 cycle 检测永远返回 `would_block=True`，导致所有 predeclared 都被报为 blocked
- 1B `GenericRegistryService.get(asset_id)` 抛 `KeyError` 是 spec 锁定的"不存在"语义，直接对应 `ORPHAN_ASSET` issue

`cascade_service` 字段仍保留在 `StoryOSDelegate.__init__` 中，作为可选附加校验（深度/循环），但不在 1C 必填范围；实施时若 1D 需要 cascade 模拟，可扩展 `validate_predeclared_changes` 在 asset 校验通过后再调 simulate。

### 5.6 1A/1B 缺失依赖的处理

本计划假设 1A/1B 全部完成。若实施时发现某个 import 缺失（如 `PredeclaredValidation`），在任务步骤中已注明临时补完方案（见 Task B2 Step 3 注）。

---

## 6. 完成判据

### 6.1 功能验收

- [ ] `ScenePlan` dataclass 存在且包含 `predeclared_changes` 字段
- [ ] `PipelineContext` 含 `scene_plan` / `storyos_active_assets` / `storyos_validation` / `storyos_bridge_result` / `storyos_failed` 5 个字段
- [ ] `StoryOSDelegate` 3 方法签名符合 spec §3.1
- [ ] `_step_build_context` 调用 `_hook_step1_context_load`
- [ ] `_step_prepare_chapter_plan` 调用 `_hook_step3_pre_write_gate`
- [ ] `_step_validate_content` 调用 `_hook_step5_post_write_gate`
- [ ] `_step_save_chapter` 完成后调用 `_hook_step6_apply_state`
- [ ] `chapter-prose-generation/package.yaml` 含 `sflog_directive` 变量 + `sflog_directive.j2` 模板
- [ ] 4 个 hook 全部降级处理（失败时记录到 `ctx.storyos_failed`）
- [ ] `StoryPipelineRunner` 通过 DI 接受 `storyos_delegate` 并注入 ctx

### 6.2 集成验收（spec §5.3）

- [ ] 端到端 happy path 4 个 hook 顺序正确
- [ ] 缺失 predeclared → Step 3 validation 报告 issues（不阻断）
- [ ] 格式错误 → Step 5 记录 format_errors（spec §4.3 A）
- [ ] bridge 失败 → Step 6 调用 `compliance_gate.record_force_pass`（spec §4.3 D）
- [ ] StoryOS 全部关闭（delegate=None）时 pipeline 不抛异常

### 6.3 测试覆盖

- [ ] `tests/unit/engine/pipeline/test_scene_plan.py` — 4 测试
- [ ] `tests/unit/engine/pipeline/test_context_scene_plan.py` — 2 测试
- [ ] `tests/unit/engine/runtime/test_storyos_delegate.py` — 12 测试（3 B1 + 5 B2 + 4 B3）
- [ ] `tests/unit/engine/runtime/test_runner_di.py` — 2 测试
- [ ] `tests/dag/storyos/test_hook_step1_context_load.py` — 2 测试
- [ ] `tests/dag/storyos/test_hook_step3_pre_write_gate.py` — 2 测试
- [ ] `tests/dag/storyos/test_hook_step5_post_write_gate.py` — 2 测试
- [ ] `tests/dag/storyos/test_hook_step6_apply_state.py` — 2 测试
- [ ] `tests/dag/storyos/test_pipeline_degraded_when_delegate_fails.py` — 2 测试
- [ ] `tests/dag/storyos/test_end_to_end_happy_path.py` — 2 测试
- [ ] `tests/integration/prompt_packages/test_chapter_prose_generation_sflog.py` — 2 测试
- [ ] `tests/integration/prompt_packages/test_prose_composer_includes_sflog.py` — 1 测试

**总计 35 测试**（9 主任务 × 平均 3-4 测试）

### 6.4 阶段输出交接清单（给 1D）

- [ ] `engine/runtime/storyos_delegate.py` 暴露 3 方法
- [ ] `ScenePlan.to_shared_state_dict()` 可在 API response 中序列化
- [ ] `sflog_directive` 注入点可在 prompt preview 中查看
- [ ] `ctx.storyos_failed` / `ctx.storyos_bridge_result` 暴露给 BFF API（1D 消费）

---

## 7. 任务依赖与并行机会

### 7.1 严格顺序（A → B → C → D）

```
A1 (ScenePlan dataclass)
  └→ A2 (PipelineContext.scene_plan)
       └→ B1 (load_active_assets) ─┐
            └→ B2 (validate_predeclared) ─┤
                 └→ B3 (apply_post_write) ─┤
                      └→ C1 (4 hooks 接入) ┤
                           └→ C2 (DI 装配) ┤
                                └→ E1 (E2E 测试) [可选，与 D 并行]
                                
D1 (sflog_directive) — 与 C 并行（无依赖）
```

### 7.2 并行机会

- **D1 (sflog_directive)** 完全独立，可与 A1-A2 / B1-B3 任何任务并行
- **E1 (E2E 测试)** 必须在 C1 + C2 完成后才能跑
- B1 / B2 / B3 内部可并行（无依赖关系），但建议顺序做以便 incremental commit

### 7.3 估时

- A1 + A2: 0.5 天
- B1 + B2 + B3: 1 天
- C1 + C2: 1 天
- D1: 0.25 天
- E1 + 集成验证: 0.25 天
- **总计: 3 天**

---

## 8. 状态

**当前状态:** 详细计划完成，等待用户 review

**下一步行动:**
1. 用户 review 通过后启动 A1 任务
2. A1 → A2 → B1 → B2 → B3 → C1 → C2 → D1 → E1 顺序执行
3. D1 可与 A/B/C 并行（独立）
4. 完成 1C 后启动 1D（前端 + API）

**估时:** 3 天（按 1 人全职计算）

---

## 9. 设计参考

- **Spec 主参考**: `../specs/2026-07-02-storyos-integration-design.md` §2.3, §3.1, §4.1, §4.3, §4.4
- **子 Spec**: `../specs/2026-07-02-storyos-asset-field-spec.md` §1, §2, §3
- **1A 阶段产出**: `./2026-07-02-storyos-phase-1a-foundation.md`（PredeclaredChange / MatchReport / SFLogRecord）
- **1B 阶段产出**: `./2026-07-02-storyos-phase-1b-application.md`（3 个核心 service + SFLogComplianceGate + ActiveAssetsContext）
- **现有 BaseStoryPipeline**: `engine/pipeline/base.py:54-1226`（10 步管线）
- **现有 ScenePlan 占位**: `engine/pipeline/beat_contracts.py:37-66`（`serialize_beats_for_shared_state`，无 predeclared_changes）
- **现有 PipelineContext**: `engine/pipeline/context.py:18-178`（无 storyos_* 字段）
- **现有 StoryPipelineRunner**: `engine/runtime/runner.py:17-167`（无 storyos_delegate DI）
- **现有 chapter-prose-generation YAML**: `infrastructure/ai/prompt_packages/nodes/chapter-prose-generation/package.yaml:11-49`（无 sflog_directive 变量）
- **1C 占位符（旧）**: 本文件 line 1-159（已废弃，被本详版完全覆盖）
- **1D 后续**: `./2026-07-02-storyos-phase-1d-frontend-api.md`（待启动）
- **1E 后续**: `./2026-07-02-storyos-phase-1e-migration.md`（占位符待详化）
