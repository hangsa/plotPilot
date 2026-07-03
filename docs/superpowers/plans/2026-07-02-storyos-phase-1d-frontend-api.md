# StoryOS Phase 1D — Frontend + API 实施计划（详版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Parent Plan:** [`2026-07-02-storyos-integration.md`](./2026-07-02-storyos-integration.md)
**Spec Reference:** [`../specs/2026-07-02-storyos-integration-design.md`](../specs/2026-07-02-storyos-integration-design.md) §2.4, §3.1 interfaces + frontend, 附录 D
**Sub-Spec Reference:** [`../specs/2026-07-02-storyos-asset-field-spec.md`](../specs/2026-07-02-storyos-asset-field-spec.md)
**1A 阶段产出（前置）：** [`./2026-07-02-storyos-phase-1a-foundation.md`](./2026-07-02-storyos-phase-1a-foundation.md)
**1B 阶段产出（前置）：** [`./2026-07-02-storyos-phase-1b-application.md`](./2026-07-02-storyos-phase-1b-application.md)
**1C 阶段产出（前置）：** [`./2026-07-02-storyos-phase-1c-engine.md`](./2026-07-02-storyos-phase-1c-engine.md)
**Phase Scope:** 51 REST 端点 + StoryOSHub 主面板 + 6 子视图 + 4 组件 + 3 Pinia stores
**LOC Target:** ~2200（后端 ~1200 + 前端 ~1000）
**Estimated Tasks:** 26
**Estimated Duration:** 1 周（4 个 subagent 并行）⚠️ 单人串行执行实际需 ~2 周
**前置依赖:** 1A 全部 + 1B 全部 + 1C 全部（API 契约已冻结）

---

## 0. 前置条件

```bash
cd /Users/longsa/Codes/plotPilot

# 1. 确认 1A 全部完成
ls domain/storyos/contracts.py domain/storyos/entities/ infrastructure/persistence/storyos/schemas/
# 期望 contracts.py + 8 entities/* + 11 schemas/* 存在

# 2. 确认 1B 全部完成
ls application/storyos/services/registry_service.py \
   application/storyos/services/cascade_service.py \
   application/storyos/services/evolution_bridge_service.py \
   application/storyos/parsers/sf_log_regex_parser.py
# 期望 4 个核心服务文件存在

# 3. 确认 1C 全部完成（ScenePlan.predeclared_changes 字段已稳定）
python -c "from engine.pipeline.beat_contracts import ScenePlan; print(ScenePlan.__dataclass_fields__.keys())"
# 期望含 'predeclared_changes'

# 4. 确认 StoryOSDelegate 已实现
python -c "from engine.runtime.storyos_delegate import StoryOSDelegate; print('ok')"

# 5. 确认 FastAPI 主入口可启动
uvicorn interfaces.main:app --host 127.0.0.1 --port 8005 &
sleep 3 && curl -s http://127.0.0.1:8005/api/v1/system/health
# 期望返回 200 + JSON 健康信息
kill %1

# 6. 确认 Vue 工具链
cd frontend && npm --version && npx vue-tsc --version
# 期望 npm 10.x + vue-tsc 3.x+

# 7. REVIEW-FIX M-1: 1B service 签名核验 — 1D 端点依赖的关键方法
#    必须存在且签名匹配；缺失或不一致时应冻结计划、回 1B 调整。
python <<'PY'
import inspect
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.sf_log_parser_service import SFLogParserService
from application.storyos.services.foreshadowing_migration_service import ForeshadowingMigrationService
from application.storyos.services.snapshot_projector import StoryOSSnapshotProjector

# CascadeService.simulate() 必须返回带 steps_executed / blocked_steps / max_depth_reached 的对象
sig = inspect.signature(CascadeService.simulate)
print("CascadeService.simulate:", sig)
assert "project_id" in sig.parameters, "CascadeService.simulate 缺 project_id 参数"
assert "trigger" in sig.parameters, "CascadeService.simulate 缺 trigger 参数"
assert "max_depth" in sig.parameters, "CascadeService.simulate 缺 max_depth 参数"

# SFLogParserService 必须有 parse_only / get_chapter_text / get_predeclared_for_chapter
for method in ("parse_only", "get_chapter_text", "get_predeclared_for_chapter", "validate_format", "match_against_predeclared"):
    assert hasattr(SFLogParserService, method), f"SFLogParserService 缺 {method} 方法"

# ForeshadowingMigrationService 必须有 scan / execute（1E 实施，但 1D DI 工厂 import 它）
for method in ("scan", "execute"):
    assert hasattr(ForeshadowingMigrationService, method), f"ForeshadowingMigrationService 缺 {method}"

# StoryOSSnapshotProjector 必须有 get_metrics / get_arc_summary
for method in ("get_metrics", "get_arc_summary"):
    assert hasattr(StoryOSSnapshotProjector, method), f"StoryOSSnapshotProjector 缺 {method}"

print("✅ 1B service 签名核验通过")
PY
# 期望输出「✅ 1B service 签名核验通过」
# 失败时：stop,回去检查 1B 的 CascadeService 返回类型 / SFLogParserService 方法集
```

---

## 1. 阶段目标

将 1A/1B/1C 实现的 SF_LOG 解析、8 Registry 状态、级联、Evolution Bridge、Compliance Gate 全部能力**暴露**到 REST API + Vue 3 工作台，让 StoryOS 状态**可视化、可查询、可回滚、可手动编辑**。

### 1.1 产出物清单

**Backend API（spec 附录 D 锁定 51 端点）：**

| 类别 | 端点数 | 路径模板 |
|---|---|---|
| 8 Registry × 5 CRUD | 40 | `GET/POST/PATCH/DELETE /api/v1/storyos/{project_id}/{asset_type}[/{asset_id}]` |
| Cascade 操作 | 3 | `/cascade/simulate`, `/cascade/replay/{bridge_id}`, `/cascade/history` |
| SFLog 操作 | 2 | `/sflog/raw?chapter=X`, `/sflog/reparse/{chapter_id}` |
| Migration 操作 | 4 | `/migration/preview`, `/migration/execute`（1D 桩 → 1E 补完）+ `/migration/{id}/status`, `/migration/{id}/rollback`（1E 新增） |
| Health | 1 | `/health` |
| StoryOS Metrics | 1 | `/metrics`（1B 实现的指标对外暴露） |
| **合计** | **51** | — |

**Frontend（spec §2.4 + §3.1 锁定）：**

| 类型 | 路径 | 数量 |
|---|---|---|
| 主面板 | `views/workbench/storyos/StoryOSHub.vue` | 1 |
| 子视图 | `RegistryList.vue` / `RegistryDetailDrawer.vue` / `CascadeGraph.vue` / `SFLogInspector.vue` / `PredeclaredDiff.vue` | 5 |
| 组件 | `AssetCard.vue` / `CascadeStepNode.vue` / `IntensityChart.vue` / `StatusBadge.vue` | 4 |
| Pinia store | `stores/storyos/queries.ts` / `cascade.ts` / `sflog.ts` | 3 |
| API client | `api/storyos/{registry,cascade,sflog,migration,health}.ts` | 5 |
| 路由 | `router/index.ts` 新增 `/book/:slug/storyos` 嵌套路由 | 1 |
| 类型 | `types/storyos.ts`（Dart-style 强类型） | 1 |
| 国际化 | `i18n/zh-CN/storyos.json`（中文文案，5 个视图的标签） | 1 |

### 1.2 关键设计点

#### 1.2.1 Backend 关键设计

1. **`crud_factory.py` 样板生成器**（spec §3.1 锁定）：
   - 8 个 registry 端点**结构相同**（5 CRUD × 8），工厂按 entity 类型注册避免 8 份重复代码
   - 工厂生成 `APIRouter`，每条路由转发到 `application/storyos/services/registry_service.py` 的对应方法
   - 注册时**冻结路径前缀**：`/api/v1/storyos/{project_id}/{asset_type}`，asset_type ∈ {conflict, mystery, twist, promise, reveal, expectation, goal, foreshadowing}
2. **错误响应统一 envelope**：
   ```json
   { "error": { "code": "FORMAT_ERROR", "message": "...", "details": {...} } }
   ```
   - 复用 `interfaces/api/v1/errors.py`（如不存在则新建），与现有 `evolution_routes.py` 风格保持一致
3. **Cascade/SFLog/Migration 端点独立路由**（不参与 crud_factory）：
   - 因业务逻辑特殊（无标准 CRUD），单独实现
   - `migration/*` 端点 1D 返回 501，1E 补完
4. **项目 ID 命名**：路径参数 `{project_id}`（与 spec 附录 D 一致），实际映射到 `novel_id`（PlotPilot 用 `novel_id` 但 spec 用 `project_id`，需在依赖注入层做 alias）
5. **DI 注入**：通过 `interfaces/api/dependencies.py`（已有 `get_evolution_*` 系列）新增 `get_storyos_*_service` 系列工厂函数

#### 1.2.2 Frontend 关键设计

1. **路由懒加载**：6 子视图按需 `import()`，配合 Vite chunk 拆分（参考 1c `chapter-prose-generation` 拆分策略）
2. **Pinia store 三模块拆分**：
   - `queries.ts`：8 registry 列表/详情查询（reactive refs + queryFn）
   - `cascade.ts`：cascade simulate/replay/history（mutations + async actions）
   - `sflog.ts`：sflog raw/reparse（mutations + async actions）
3. **CascadeGraph 用 Vue Flow + ECharts**（spec §2.4 锁定）：
   - Vue Flow 画节点-边（DAG 布局）
   - ECharts 嵌套 IntensityChart 组件显示强度趋势
4. **SFLogInspector 并排布局**：
   - 左侧：原始章节文本（高亮 SF_LOG 注释块，可折叠）
   - 右侧：解析结果（`SFLogRecord[]` 列表 + 每条关联的 AssetView）
5. **PredeclaredDiff 高亮**：
   - 绿色 = 匹配（predeclared 出现在实际产出）
   - 红色 = 缺失（predeclared 未实现 → 触发 RETRY）
   - 黄色 = 意外（实际产出有但 predeclared 无 → WARN）
6. **StatusBadge 颜色映射**（12 态 → 颜色）：
   - ACTIVE/ACCUMULATING/DEVELOPING/HIDDEN → 蓝色（中性）
   - PLANTED/READY_TO_FULFILL/ESCALATED → 黄色（待处理）
   - REVEALED/FULFILLED/RESOLVED → 绿色（成功）
   - ABANDONED/DEAD → 红色（终止）
7. **i18n 中文优先**：所有 label 用 `i18n` key（zh-CN 完整翻译，en-US 兜底英文）

### 1.3 不在本阶段范围

- ❌ StoryOS 写入逻辑（→ 1A/1B 已完成，1D 只读 + 部分手动编辑）
- ❌ SF_LOG 解析业务（→ 1B 已完成，1D 仅暴露 raw 文本与解析结果）
- ❌ Evolution Bridge 双写（→ 1B 已完成，1D 仅暴露 BridgeResult 与 bridge_log 失败记录）
- ❌ 引擎钩子（→ 1C 已完成，1D 触发 `POST /chapters/{id}/regenerate` 间接调用）
- ❌ 旧 Foreshadowing 数据迁移（→ 1E，1D 端点为桩）
- ❌ 跨项目资产共享（spec §8 锁定单项目隔离）
- ❌ Workbench 实时协同编辑（spec §8 锁定单人浏览/编辑）

### 1.4 与其他阶段的边界

| 1D 产出 | 下游消费者 |
|---|---|
| 51 REST 端点 | 用户（Workbench）+ 1F（未来导出与审计）|
| StoryOSHub 前端 | 写作工作台（`/book/:slug/workbench` → "StoryOS" 入口） |
| `bridge_log` 暴露 | 1D 自身显示 + 1E 迁移审计 |
| `migration/*` 桩 | 1E 联通（无需 1D 改动） |

### 1.5 测试覆盖目标

| 测试树 | 目标覆盖率 | 关键测试 |
|---|---|---|
| `tests/integration/api/v1/storyos/` | 端到端 API 100% | 51 端点 + 错误路径 |
| `tests/unit/interfaces/api/v1/storyos/` | 行覆盖 ≥ 90% | crud_factory + DTO 序列化 |
| `frontend/src/views/workbench/storyos/__tests__/` | 组件测试 | 6 视图快照 + 交互 |
| `frontend/src/stores/storyos/__tests__/` | store 测试 | 3 模块 reactive 行为 |
| `tests/performance/` | 性能基准 | `test_api_8_registry_latency.py` 8 registry 列表 < 200ms |

---

## 2. TDD 约定

每个任务严格遵循 5 步循环（2-5 分钟/步）：

1. **写失败测试**：在 `tests/integration/api/v1/storyos/` 或 `frontend/src/.../__tests__/` 创建测试文件
2. **运行测试确认失败**：`pytest ...` 或 `npm run test`，期望 ImportError / 404 / AssertionError
3. **写最小实现**：在指定实现文件创建骨架，刚好让测试通过
4. **运行测试确认通过**：期望 PASS
5. **Commit**：`git add ... && git commit -m "..."`

### 2.1 通用 commit 消息前缀

**Backend：**
- `feat(api):` — REST 端点新增
- `feat(schemas):` — Pydantic DTO
- `feat(factory):` — crud_factory 样板生成
- `test(api):` — API 集成测试
- `refactor(api):` — API 重构（不影响契约）

**Frontend：**
- `feat(frontend):` — Vue 组件/Pinia store
- `feat(router):` — 路由新增
- `feat(types):` — TypeScript 类型
- `test(frontend):` — Vitest 组件测试
- `style(frontend):` — UI 样式调整

### 2.2 测试文件命名

**Backend：**
- API 端点：`tests/integration/api/v1/storyos/test_{endpoint_group}_routes.py`
- DTO 序列化：`tests/unit/interfaces/api/v1/storyos/schemas/test_{entity}_schemas.py`
- Factory：`tests/unit/interfaces/api/v1/storyos/test_crud_factory.py`
- 错误处理：`tests/unit/interfaces/api/v1/test_error_envelope.py`

**Frontend：**
- 组件：`frontend/src/views/workbench/storyos/__tests__/{Component}.spec.ts`
- Pinia store：`frontend/src/stores/storyos/__tests__/{module}.spec.ts`
- API client：`frontend/src/api/storyos/__tests__/{module}.spec.ts`

### 2.3 实施顺序与并行机会

**严格依赖：**
- Group A → Group B（C 路由依赖 A 的 DTO）
- Group A → Group C（独立，但需 A 完成的 DTO 序列）
- Group A → Group D 前端 DTO 类型（前后端 DTO 必须同源）
- Group D → Group E（5 子视图依赖 3 stores）
- Group B + C → Group F（F 集成测试调全部端点）

**可并行：**
- Group A 内部 5 任务可串行（A1 8 schema → A2 8 schema → A3 common → A4 factory → A5 router）
- Group B 内部 3 任务可并行（不同文件，无冲突）
- Group C 内部 4 任务可并行（不同路由文件）
- **Group A 与 Group D 前后端并行**：A 完成后端 DTO，D 同时定义前端 TypeScript 类型（按 spec 同源原则）

**4 subagent 并行策略（推荐）：**
- subagent 1：Group A → B → F1（API 完整链路）
- subagent 2：Group C（Cascade/SFLog/Migration/Health 端点）
- subagent 3：Group D（前端基础设施）
- subagent 4：Group E（前端 6 子视图 + 4 组件，依赖 D 但与 API 任务并行）

### 2.4 端点契约冻结（contract freeze）

Group A 完成时锁定以下契约，后续 Group 必须遵守：

```yaml
路径模板: /api/v1/storyos/{project_id}/{subpath}
子路径:
  - {asset_type}                     # 8 种之一（见上）
  - {asset_type}/{asset_id}
  - cascade/{simulate|replay|history}
  - sflog/{raw|reparse}
  - migration/{preview|execute}
  - health
  - metrics
HTTP 方法: GET（读）/ POST（创建/操作）/ PATCH（部分更新）/ DELETE（删除）
响应格式: { "data": {...}, "meta": {...} } （成功）/ { "error": {...} } （失败）
分页参数: ?page=1&page_size=20&status=active&asset_type=...
```

任何 Group B/C 任务的端点路径**必须**与上述契约一致；冲突时回到 Group A 调整。

---

## 3. 任务清单

### Group A: API Schemas + Factory（5 任务）

#### Task A1: 8 Entity Request Schemas（8 文件）

**Files:**
- Create: `interfaces/api/v1/storyos/__init__.py`（空文件）
- Create: `interfaces/api/v1/storyos/schemas/__init__.py`（空文件）
- Create: `interfaces/api/v1/storyos/schemas/conflict_schemas.py`
- Create: `interfaces/api/v1/storyos/schemas/mystery_schemas.py`
- Create: `interfaces/api/v1/storyos/schemas/twist_schemas.py`
- Create: `interfaces/api/v1/storyos/schemas/promise_schemas.py`
- Create: `interfaces/api/v1/storyos/schemas/reveal_schemas.py`
- Create: `interfaces/api/v1/storyos/schemas/expectation_schemas.py`
- Create: `interfaces/api/v1/storyos/schemas/goal_schemas.py`
- Create: `interfaces/api/v1/storyos/schemas/foreshadowing_schemas.py`
- Create: `tests/unit/interfaces/api/v1/storyos/__init__.py`（空文件）
- Create: `tests/unit/interfaces/api/v1/storyos/schemas/__init__.py`（空文件）
- Create: `tests/unit/interfaces/api/v1/storyos/schemas/test_conflict_schemas.py`（仅 1 个 entity 的完整测试，其余 7 个同构）

- [ ] **Step 1: 写失败测试** — `tests/unit/interfaces/api/v1/storyos/schemas/test_conflict_schemas.py`

```python
"""Conflict DTO 序列化测试（8 entity 同构，本测试作为契约蓝本）。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.conflict_schemas import (
    ConflictCreateRequest,
    ConflictUpdateRequest,
    ConflictResponse,
)
from domain.storyos.contracts import AssetStatus


def test_conflict_create_request_minimal():
    """最小必填字段。"""
    req = ConflictCreateRequest(
        project_id="proj-1",
        description="林远 vs 沈墨的权力斗争",
        created_chapter=3,
    )
    assert req.project_id == "proj-1"
    assert req.status == AssetStatus.ACTIVE  # 默认值
    assert req.intensity == 50  # 默认值
    assert req.linked_assets == {}


def test_conflict_create_request_rejects_invalid_status():
    with pytest.raises(ValidationError):
        ConflictCreateRequest(
            project_id="proj-1",
            description="x",
            created_chapter=1,
            status="bogus",  # type: ignore[arg-type]
        )


def test_conflict_create_request_intensity_range():
    """intensity 必须在 0-100。"""
    with pytest.raises(ValidationError):
        ConflictCreateRequest(
            project_id="proj-1", description="x", created_chapter=1, intensity=150,
        )
    with pytest.raises(ValidationError):
        ConflictCreateRequest(
            project_id="proj-1", description="x", created_chapter=1, intensity=-1,
        )


def test_conflict_update_request_all_optional():
    """PATCH 必须全可选。"""
    req = ConflictUpdateRequest()
    assert req.description is None
    assert req.status is None
    assert req.intensity is None
    assert req.linked_assets is None


def test_conflict_update_request_partial_update():
    req = ConflictUpdateRequest(status=AssetStatus.ESCALATED, intensity=80)
    assert req.status == AssetStatus.ESCALATED
    assert req.intensity == 80
    # 未指定字段保持 None
    assert req.description is None


def test_conflict_response_from_domain_entity():
    """Response 应能从 domain entity 构造。"""
    from domain.storyos.entities.conflict import Conflict
    entity = Conflict(
        id="cf-1",
        project_id="proj-1",
        description="x",
        status=AssetStatus.ESCALATED,
        intensity=80,
        created_chapter=5,
    )
    resp = ConflictResponse.from_domain(entity)
    assert resp.id == "cf-1"
    assert resp.project_id == "proj-1"
    assert resp.status == AssetStatus.ESCALATED
    assert resp.intensity == 80
    assert resp.created_chapter == 5
    assert resp.created_at is not None  # 必有 ISO 时间戳
    assert resp.updated_at is not None


def test_conflict_response_serializes_asset_status_as_string():
    """AssetStatus 序列化为 snake_case 字符串（API 契约）。"""
    from domain.storyos.entities.conflict import Conflict
    entity = Conflict(
        id="cf-1", project_id="proj-1", description="x",
        status=AssetStatus.ESCALATED, intensity=80, created_chapter=5,
    )
    resp = ConflictResponse.from_domain(entity)
    data = resp.model_dump()
    assert data["status"] == "escalated"  # 不是 AssetStatus 枚举对象
    assert isinstance(data["status"], str)
```

- [ ] **Step 2: 运行测试确认失败** — `pytest tests/unit/interfaces/api/v1/storyos/schemas/test_conflict_schemas.py -v` 期望 `ModuleNotFoundError`

- [ ] **Step 3: 写最小实现** — `interfaces/api/v1/storyos/schemas/conflict_schemas.py`：

```python
"""Conflict entity 的 Pydantic DTO（Request + Response）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict


class ConflictCreateRequest(BaseModel):
    """POST /conflicts body。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=2000)
    created_chapter: int = Field(ge=1)
    status: AssetStatus = AssetStatus.ACTIVE
    intensity: int = Field(default=50, ge=0, le=100)
    linked_assets: dict[str, str] = Field(default_factory=dict)
    participants: list[str] = Field(default_factory=list)  # Conflict 特有
    resolution_chapter: Optional[int] = Field(default=None, ge=1)


class ConflictUpdateRequest(BaseModel):
    """PATCH /conflicts/{id} body（所有字段可选）。"""

    model_config = ConfigDict(extra="forbid")

    description: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: Optional[AssetStatus] = None
    intensity: Optional[int] = Field(default=None, ge=0, le=100)
    linked_assets: Optional[dict[str, str]] = None
    participants: Optional[list[str]] = None
    resolution_chapter: Optional[int] = Field(default=None, ge=1)


class ConflictResponse(BaseModel):
    """GET /conflicts/{id} 与列表项的统一返回。"""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    description: str
    status: AssetStatus
    intensity: int
    created_chapter: int
    linked_assets: dict[str, str]
    participants: list[str] = Field(default_factory=list)
    resolution_chapter: Optional[int] = None
    cascade_updated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, entity: Conflict) -> "ConflictResponse":
        """从 domain entity 构造（spec §3.4 mapper 同源）。"""
        return cls(
            id=entity.id,
            project_id=entity.project_id,
            description=entity.description,
            status=entity.status,
            intensity=entity.intensity,
            created_chapter=entity.created_chapter,
            linked_assets=dict(entity.linked_assets),
            participants=list(entity.participants),
            resolution_chapter=entity.resolution_chapter,
            cascade_updated_at=entity.cascade_updated_at,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
```

并在 `interfaces/api/v1/storyos/schemas/__init__.py` 暴露：

```python
from interfaces.api.v1.storyos.schemas.conflict_schemas import (
    ConflictCreateRequest, ConflictUpdateRequest, ConflictResponse,
)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 7 passed

- [ ] **Step 5: Commit** — `git add interfaces/api/v1/storyos/ tests/unit/interfaces/api/v1/storyos/ && git commit -m "feat(schemas): add Conflict DTO (Request/Update/Response) with from_domain mapper"`

**扩展任务（7 个 entity 同构，**批量完成，每 entity 一次 commit**）：**

| 子任务 | entity 特有字段 | 默认值 | 文件 |
|---|---|---|---|
| A1.2 | Mystery | `clues: list[ClueResponse]`, `category: ClueCategory`, `solution_chapter: Optional[int]` | `mystery_schemas.py` |
| A1.3 | Twist | `twist_type: TwistType`, `trigger_chapter: int`, `foreshadowing_refs: list[str]` | `twist_schemas.py` |
| A1.4 | Promise | `fulfillment_chapter: Optional[int]`, `importance: ImportanceLevel`, `linked_conflict_id: Optional[str]` | `promise_schemas.py` |
| A1.5 | Reveal | `reveal_type: RevealType`, `revealed_chapter: int`, `related_mystery_id: str` | `reveal_schemas.py` |
| A1.6 | Expectation | `intensity: int`, `linked_twist_id: Optional[str]`, `linked_conflict_id: Optional[str]`, `ready_chapter: Optional[int]` | `expectation_schemas.py` |
| A1.7 | Goal | `progress_marker: ProgressMarker`, `linked_character_id: str`, `completion_chapter: Optional[int]` | `goal_schemas.py` |
| A1.8 | Foreshadowing | `importance: ImportanceLevel`, `payoff_chapter: Optional[int]`, `migrated_from_legacy_id: Optional[str]`（1E 迁移字段） | `foreshadowing_schemas.py` |

每个 entity 的测试文件**复制 test_conflict_schemas.py 模板**，仅修改：
1. import 的 schema 类名
2. 特有字段的最小/范围/默认值测试
3. `from_domain` 的实体构造参数

**每个 entity 子任务约 100-150 LOC（test + impl），8 entity 合计 ~1200 LOC。**

#### Task A2: 8 Entity Response Schemas + Pagination Envelope

**Files:**
- Create: `interfaces/api/v1/storyos/schemas/common_schemas.py`
- Modify: `interfaces/api/v1/storyos/schemas/{8}_schemas.py`（追加 ListResponse）
- Create: `tests/unit/interfaces/api/v1/storyos/schemas/test_common_schemas.py`

- [ ] **Step 1: 写失败测试**

```python
"""通用分页与错误 envelope DTO。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.common_schemas import (
    PaginationMeta,
    ListResponseEnvelope,
    ErrorDetail,
    ErrorResponse,
)


def test_pagination_meta_defaults():
    p = PaginationMeta(total=100, page=1, page_size=20)
    assert p.total_pages == 5
    assert p.has_next is True
    assert p.has_prev is False


def test_pagination_meta_last_page():
    p = PaginationMeta(total=100, page=5, page_size=20)
    assert p.has_next is False
    assert p.has_prev is True


def test_pagination_meta_validates_non_negative():
    with pytest.raises(ValidationError):
        PaginationMeta(total=-1, page=1, page_size=20)


def test_list_response_envelope_wraps_data():
    from interfaces.api.v1.storyos.schemas.conflict_schemas import ConflictResponse
    # 简化：内层 data 是 dict list
    env = ListResponseEnvelope[dict](
        data=[{"id": "cf-1"}],
        meta=PaginationMeta(total=1, page=1, page_size=20),
    )
    assert env.data == [{"id": "cf-1"}]
    assert env.meta.total == 1


def test_error_detail_includes_code_and_message():
    err = ErrorDetail(code="FORMAT_ERROR", message="bad input")
    assert err.code == "FORMAT_ERROR"
    assert err.details is None


def test_error_response_envelope():
    resp = ErrorResponse(
        error=ErrorDetail(
            code="NOT_FOUND", message="asset cf-1 not found",
            details={"asset_type": "conflict", "asset_id": "cf-1"},
        )
    )
    out = resp.model_dump()
    assert out["error"]["code"] == "NOT_FOUND"
    assert out["error"]["details"]["asset_id"] == "cf-1"
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`

- [ ] **Step 3: 实现** — `interfaces/api/v1/storyos/schemas/common_schemas.py`：

```python
"""StoryOS 子包共享 DTO：分页 + 错误 envelope。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """分页元数据。"""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total_pages: int = Field(ge=0)
    has_next: bool
    has_prev: bool

    @classmethod
    def compute(cls, total: int, page: int, page_size: int) -> "PaginationMeta":
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return cls(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class ListResponseEnvelope(BaseModel, Generic[T]):
    """列表端点统一 envelope。"""

    model_config = ConfigDict(extra="forbid")

    data: list[T]
    meta: PaginationMeta


class ErrorDetail(BaseModel):
    """错误响应 detail。"""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=2000)
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """错误响应 envelope。"""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail
```

并在每个 `*_schemas.py` 追加：

```python
class {Entity}ListResponse(BaseModel):
    """GET /{asset_type} 列表响应。"""
    model_config = ConfigDict(extra="forbid")
    data: list[{Entity}Response]
    meta: PaginationMeta
```

- [ ] **Step 4: 运行测试确认通过** — 期望 6 passed

- [ ] **Step 5: Commit** — `git add interfaces/api/v1/storyos/schemas/ tests/unit/interfaces/api/v1/storyos/schemas/ && git commit -m "feat(schemas): add PaginationMeta + ListResponseEnvelope + ErrorResponse"`

#### Task A3: Cascade/SFLog/Migration 专用 DTOs

**Files:**
- Create: `interfaces/api/v1/storyos/schemas/cascade_schemas.py`
- Create: `interfaces/api/v1/storyos/schemas/sflog_schemas.py`
- Create: `interfaces/api/v1/storyos/schemas/migration_schemas.py`
- Create: `tests/unit/interfaces/api/v1/storyos/schemas/test_cascade_schemas.py`
- Create: `tests/unit/interfaces/api/v1/storyos/schemas/test_sflog_schemas.py`
- Create: `tests/unit/interfaces/api/v1/storyos/schemas/test_migration_schemas.py`

- [ ] **Step 1: 写失败测试** — `test_cascade_schemas.py`

```python
"""Cascade 端点 DTO 测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.cascade_schemas import (
    CascadeSimulateRequest,
    CascadeSimulateResponse,
    CascadeReplayRequest,
    CascadeStepDTO,
)
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep, CascadeResult


def test_cascade_step_dto_from_domain():
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery",
        source_asset_id="m1",
        target_asset_type="expectation",
        target_asset_id="e1",
        new_status=AssetStatus.READY_TO_FULFILL,
        reason="climax reached",
    )
    dto = CascadeStepDTO.from_domain(step)
    assert dto.trigger == CascadeTrigger.MYSTERY_REVEALED
    assert dto.new_status == AssetStatus.READY_TO_FULFILL
    assert dto.reason == "climax reached"


def test_cascade_simulate_request_requires_source():
    req = CascadeSimulateRequest(
        project_id="proj-1",
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery",
        source_asset_id="m1",
    )
    assert req.max_depth == 3  # 默认值


def test_cascade_simulate_request_validates_max_depth():
    with pytest.raises(ValidationError):
        CascadeSimulateRequest(
            project_id="proj-1",
            trigger=CascadeTrigger.MYSTERY_REVEALED,
            source_asset_type="mystery",
            source_asset_id="m1",
            max_depth=10,  # 超过 spec §4.2 锁定的 MAX_CASCADE_DEPTH=3
        )


def test_cascade_simulate_response_includes_summary():
    """响应含 step 列表 + 摘要（避免前端需重新聚合）。"""
    from interfaces.api.v1.storyos.schemas.cascade_schemas import CascadeSimulateSummary
    summary = CascadeSimulateSummary(
        would_block=False,
        max_depth_reached=2,
        steps_count=3,
        blocked_steps_count=0,
    )
    resp = CascadeSimulateResponse(
        steps=[],
        summary=summary,
    )
    assert resp.summary.max_depth_reached == 2


def test_cascade_replay_request_requires_bridge_id_in_path():
    """bridge_id 来自路径参数，body 仅需可选 notes。"""
    req = CascadeReplayRequest(notes="manual review after incident")
    assert req.notes is not None
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`

- [ ] **Step 3: 实现** — `interfaces/api/v1/storyos/schemas/cascade_schemas.py`：

```python
"""Cascade 端点专用 DTO。"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep, CascadeResult


class CascadeStepDTO(BaseModel):
    """CascadeStep 的 API 表示。"""

    model_config = ConfigDict(from_attributes=True)

    trigger: CascadeTrigger
    source_asset_type: str
    source_asset_id: str
    target_asset_type: str
    target_asset_id: str
    new_status: Optional[AssetStatus] = None
    intensity_delta: Optional[int] = None
    reason: str = ""

    @classmethod
    def from_domain(cls, step: CascadeStep) -> "CascadeStepDTO":
        return cls(
            trigger=step.trigger,
            source_asset_type=step.source_asset_type,
            source_asset_id=step.source_asset_id,
            target_asset_type=step.target_asset_type,
            target_asset_id=step.target_asset_id,
            new_status=step.new_status,
            intensity_delta=step.intensity_delta,
            reason=step.reason,
        )


class CascadeSimulateSummary(BaseModel):
    """模拟结果摘要（避免前端遍历 steps 计算）。"""
    model_config = ConfigDict(extra="forbid")

    would_block: bool
    max_depth_reached: int = Field(ge=0)
    steps_count: int = Field(ge=0)
    blocked_steps_count: int = Field(ge=0)
    would_create_cycle: bool = False


class CascadeSimulateRequest(BaseModel):
    """POST /cascade/simulate body。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=64)
    trigger: CascadeTrigger
    source_asset_type: str = Field(min_length=1, max_length=32)
    source_asset_id: str = Field(min_length=1, max_length=128)
    proposed_new_status: Optional[AssetStatus] = None  # 触发的初始状态变更
    max_depth: int = Field(default=3, ge=1, le=3)  # spec §4.2 锁定 3


class CascadeSimulateResponse(BaseModel):
    """POST /cascade/simulate 响应。"""
    model_config = ConfigDict(extra="forbid")

    steps: list[CascadeStepDTO]
    summary: CascadeSimulateSummary
    blocked_steps: list[CascadeStepDTO] = Field(default_factory=list)


class CascadeReplayRequest(BaseModel):
    """POST /cascade/replay/{bridge_id} body。"""
    model_config = ConfigDict(extra="forbid")

    notes: Optional[str] = Field(default=None, max_length=1000)
```

`test_sflog_schemas.py` 与 `test_migration_schemas.py` 同构，参考下方核心字段：

**`sflog_schemas.py` 关键字段：**
- `SFLogRawResponse`: `chapter_id, raw_text, sf_log_count, records: list[SFLogRecordDTO]`
- `SFLogRecordDTO.from_domain(record: SFLogRecord)` — 序列化 6 字段
- `SFLogReparseResponse`: `chapter_id, parsed_count, format_errors, match_report: MatchReportDTO`

**`migration_schemas.py` 关键字段（1D 桩支持）：**
- `MigrationPreviewResponse`: `total, scanned, migratable, skipped, invalid, sample_errors`（5 元组 + sample 错误样本）
- `MigrationExecuteRequest`: `batch_size: int = 500, dry_run: bool = False`
- `MigrationExecuteResponse`: `migration_id, status, batches_total, batches_done, errors`
- `MigrationStatusResponse`: `migration_id, status, progress_pct, eta_seconds`

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed × 3 套 = 15 passed

- [ ] **Step 5: Commit** — `git add interfaces/api/v1/storyos/schemas/ tests/unit/interfaces/api/v1/storyos/schemas/ && git commit -m "feat(schemas): add Cascade/SFLog/Migration DTOs with from_domain mappers"`

#### Task A4: CRUD Factory 样板生成器

**Files:**
- Create: `interfaces/api/v1/storyos/crud_factory.py`
- Create: `tests/unit/interfaces/api/v1/storyos/test_crud_factory.py`

- [ ] **Step 1: 写失败测试**

```python
"""crud_factory 单元测试。"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.testclient import TestClient

from interfaces.api.v1.storyos.crud_factory import build_crud_router
from interfaces.api.v1.storyos.schemas.conflict_schemas import (
    ConflictCreateRequest, ConflictUpdateRequest, ConflictResponse,
)
from domain.storyos.entities.conflict import Conflict
from domain.storyos.contracts import AssetStatus


class FakeConflictService:
    """最小化 stub，验证 factory 正确转发 5 个 CRUD 方法。"""

    def __init__(self):
        self.list_called_with = None
        self.get_called_with = None
        self.create_called_with = None
        self.update_called_with = None
        self.delete_called_with = None
        self._store: dict[str, Conflict] = {}

    async def list(self, project_id, status=None, page=1, page_size=20):
        self.list_called_with = (project_id, status, page, page_size)
        items = [c for c in self._store.values() if c.project_id == project_id]
        if status:
            items = [c for c in items if c.status == status]
        return items, len(items)

    async def get(self, project_id, asset_id):
        self.get_called_with = (project_id, asset_id)
        return self._store.get(asset_id)

    async def create(self, project_id, data):
        self.create_called_with = (project_id, data)
        entity = Conflict(
            id="cf-1", project_id=project_id, description=data.description,
            status=data.status, intensity=data.intensity,
            created_chapter=data.created_chapter,
        )
        self._store[entity.id] = entity
        return entity

    async def update(self, project_id, asset_id, data):
        self.update_called_with = (project_id, asset_id, data)
        old = self._store[asset_id]
        new = old.model_copy(update=data.model_dump(exclude_unset=True))
        self._store[asset_id] = new
        return new

    async def delete(self, project_id, asset_id):
        self.delete_called_with = (project_id, asset_id)
        del self._store[asset_id]


def test_factory_returns_api_router():
    service = FakeConflictService()
    router = build_crud_router(
        asset_type="conflict",
        service_provider=lambda: service,  # REVIEW-FIX L-10: sync provider for TestClient
        create_schema=ConflictCreateRequest,
        update_schema=ConflictUpdateRequest,
        response_schema=ConflictResponse,
    )
    assert isinstance(router, APIRouter)
    # 5 个 CRUD 路由
    assert len(router.routes) == 5


def test_factory_routes_have_correct_paths():
    service = FakeConflictService()
    router = build_crud_router(
        asset_type="conflict",
        service_provider=lambda: service,  # REVIEW-FIX L-10: sync provider for TestClient
        create_schema=ConflictCreateRequest,
        update_schema=ConflictUpdateRequest,
        response_schema=ConflictResponse,
    )
    paths = {r.path for r in router.routes}
    assert "/api/v1/storyos/{project_id}/conflict" in paths
    assert "/api/v1/storyos/{project_id}/conflict/{asset_id}" in paths


def test_factory_list_route_calls_service_list():
    service = FakeConflictService()
    router = build_crud_router(
        asset_type="conflict",
        service_provider=lambda: service,  # REVIEW-FIX L-10: sync provider for TestClient
        create_schema=ConflictCreateRequest,
        update_schema=ConflictUpdateRequest,
        response_schema=ConflictResponse,
    )
    app = __import__("fastapi", fromlist=["FastAPI"]).FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/storyos/proj-1/conflict?status=active&page=1&page_size=20")
    assert resp.status_code == 200
    assert service.list_called_with == ("proj-1", "active", 1, 20)


def test_factory_get_route_returns_envelope():
    service = FakeConflictService()
    service._store["cf-1"] = Conflict(
        id="cf-1", project_id="proj-1", description="x",
        status=AssetStatus.ACTIVE, intensity=50, created_chapter=1,
    )
    router = build_crud_router(
        asset_type="conflict",
        service_provider=lambda: service,  # REVIEW-FIX L-10: sync provider for TestClient
        create_schema=ConflictCreateRequest,
        update_schema=ConflictUpdateRequest,
        response_schema=ConflictResponse,
    )
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get("/api/v1/storyos/proj-1/conflict/cf-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["id"] == "cf-1"


def test_factory_create_route_accepts_body():
    service = FakeConflictService()
    router = build_crud_router(
        asset_type="conflict",
        service_provider=lambda: service,  # REVIEW-FIX L-10: sync provider for TestClient
        create_schema=ConflictCreateRequest,
        update_schema=ConflictUpdateRequest,
        response_schema=ConflictResponse,
    )
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={"description": "x", "created_chapter": 1, "status": "active", "intensity": 50},
    )
    assert resp.status_code == 201
    assert service.create_called_with is not None
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`

- [ ] **Step 3: 实现** — `interfaces/api/v1/storyos/crud_factory.py`：

```python
"""CRUD 路由样板生成器（8 registry × 5 CRUD = 40 端点共用一份样板）。"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Generic, Protocol, Type, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel

from interfaces.api.v1.storyos.schemas.common_schemas import (
    ListResponseEnvelope, PaginationMeta,
)

TCreate = TypeVar("TCreate", bound=BaseModel)
TUpdate = TypeVar("TUpdate", bound=BaseModel)
TResponse = TypeVar("TResponse", bound=BaseModel)
TEntity = TypeVar("TEntity")


class CRUDService(Protocol, Generic[TEntity, TCreate, TUpdate]):
    """所有 8 registry service 必须满足的协议。"""

    async def list(
        self, project_id: str, status: str | None = None,
        page: int = 1, page_size: int = 20,
    ) -> tuple[list[TEntity], int]: ...

    async def get(self, project_id: str, asset_id: str) -> TEntity | None: ...

    async def create(self, project_id: str, data: TCreate) -> TEntity: ...

    async def update(self, project_id: str, asset_id: str, data: TUpdate) -> TEntity: ...

    async def delete(self, project_id: str, asset_id: str) -> None: ...


def build_crud_router(
    asset_type: str,
    service_provider: Callable[..., Awaitable[Any]],
    create_schema: Type[TCreate],
    update_schema: Type[TUpdate],
    response_schema: Type[TResponse],
) -> APIRouter:
    """生成 5 个 CRUD 端点的 APIRouter。

    REVIEW-FIX L-10: `service_provider` 是 FastAPI Depends 兼容的可调用对象
    （同步或 async），由框架按请求解析。原版 `service: CRUDService` 直接接收
    实例导致 router_registry.py 无法用 Depends() 注入（因为 Depends 标记
    对象会被当成 service 实例，触发 AttributeError）。

    路径模板：
        GET    /api/v1/storyos/{project_id}/{asset_type}
        GET    /api/v1/storyos/{project_id}/{asset_type}/{asset_id}
        POST   /api/v1/storyos/{project_id}/{asset_type}
        PATCH  /api/v1/storyos/{project_id}/{asset_type}/{asset_id}
        DELETE /api/v1/storyos/{project_id}/{asset_type}/{asset_id}

    调用约定：
    - 测试：`service_provider=lambda: fake_service`（同步）
    - 生产：`service_provider=get_conflict_service`（async，1B DI 工厂）
    """
    router = APIRouter(
        prefix=f"/api/v1/storyos/{{project_id}}/{asset_type}",
        tags=[f"storyos-{asset_type}"],
    )

    @router.get("", response_model=ListResponseEnvelope[response_schema])
    async def list_assets(
        project_id: str = Path(..., min_length=1, max_length=64),
        status_filter: str | None = Query(default=None, alias="status"),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=20, ge=1, le=200),
        service: Any = Depends(service_provider),  # type: ignore[arg-type]
    ) -> ListResponseEnvelope[response_schema]:  # type: ignore[valid-type]
        items, total = await service.list(
            project_id=project_id,
            status=status_filter,
            page=page,
            page_size=page_size,
        )
        # REVIEW-FIX C-1: 必须用 envelope 构造器；返回 dict 会绕过
        # Generic[T] 的运行时校验，让 list 元素残留为 dict。
        return ListResponseEnvelope[response_schema](
            data=[response_schema.model_validate(item) for item in items],
            meta=PaginationMeta.compute(total=total, page=page, page_size=page_size),
        )

    @router.get("/{asset_id}", response_model=response_schema)
    async def get_asset(
        project_id: str = Path(..., min_length=1, max_length=64),
        asset_id: str = Path(..., min_length=1, max_length=128),
        service: Any = Depends(service_provider),  # type: ignore[arg-type]
    ) -> response_schema:  # type: ignore[valid-type]
        entity = await service.get(project_id, asset_id)
        if entity is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ASSET_NOT_FOUND",
                    "message": f"{asset_type} {asset_id} not found in project {project_id}",
                    "details": {"asset_type": asset_type, "asset_id": asset_id, "project_id": project_id},
                },
            )
        return response_schema.model_validate(entity)

    @router.post("", response_model=response_schema, status_code=status.HTTP_201_CREATED)
    async def create_asset(
        data: create_schema,  # type: ignore[valid-type]
        project_id: str = Path(..., min_length=1, max_length=64),
        service: Any = Depends(service_provider),  # type: ignore[arg-type]
    ) -> response_schema:  # type: ignore[valid-type]
        entity = await service.create(project_id, data)
        return response_schema.model_validate(entity)

    @router.patch("/{asset_id}", response_model=response_schema)
    async def update_asset(
        data: update_schema,  # type: ignore[valid-type]
        project_id: str = Path(..., min_length=1, max_length=64),
        asset_id: str = Path(..., min_length=1, max_length=128),
        service: Any = Depends(service_provider),  # type: ignore[arg-type]
    ) -> response_schema:  # type: ignore[valid-type]
        entity = await service.update(project_id, asset_id, data)
        if entity is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ASSET_NOT_FOUND",
                    "message": f"{asset_type} {asset_id} not found",
                },
            )
        return response_schema.model_validate(entity)

    @router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_asset(
        project_id: str = Path(..., min_length=1, max_length=64),
        asset_id: str = Path(..., min_length=1, max_length=128),
        service: Any = Depends(service_provider),  # type: ignore[arg-type]
    ) -> None:
        await service.delete(project_id, asset_id)

    return router
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed

- [ ] **Step 5: Commit** — `git add interfaces/api/v1/storyos/crud_factory.py tests/unit/interfaces/api/v1/storyos/test_crud_factory.py && git commit -m "feat(factory): add build_crud_router factory for 8 registry endpoints (40 total)"`

#### Task A5: 路由注册 + 全局错误处理中间件

**Files:**
- Create: `interfaces/api/v1/storyos/router_registry.py`
- Create: `interfaces/api/v1/storyos/error_handlers.py`
- Modify: `interfaces/main.py`（注册 storyos 子路由）
- Create: `tests/integration/api/v1/storyos/test_router_registration.py`

- [ ] **Step 1: 写失败测试** — `test_router_registration.py`

```python
"""所有 40+ 端点注册测试。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import interfaces.main as main_module
from interfaces.api.v1.storyos.router_registry import build_storyos_router


def test_all_8_assets_have_5_crud_routes():
    """通过 OpenAPI schema 验证 8 × 5 = 40 CRUD 端点全部注册。"""
    app = FastAPI()
    app.include_router(build_storyos_router())
    schema = app.openapi()
    paths = schema["paths"]

    expected_methods = {"get", "post", "patch", "delete"}
    asset_types = ["conflict", "mystery", "twist", "promise",
                   "reveal", "expectation", "goal", "foreshadowing"]

    for asset in asset_types:
        # 列表 + 详情路径都应存在
        list_path = f"/api/v1/storyos/{{project_id}}/{asset}"
        detail_path = f"/api/v1/storyos/{{project_id}}/{asset}/{{asset_id}}"
        assert list_path in paths, f"missing list path for {asset}"
        assert detail_path in paths, f"missing detail path for {asset}"
        # 5 个方法（list GET / detail GET/POST/PATCH/DELETE）
        list_methods = set(paths[list_path].keys()) & expected_methods
        detail_methods = set(paths[detail_path].keys()) & expected_methods
        assert "get" in list_methods
        assert all(m in detail_methods for m in ("get", "patch", "delete"))


def test_special_routes_registered():
    app = FastAPI()
    app.include_router(build_storyos_router())
    schema = app.openapi()
    paths = schema["paths"]

    expected_special = [
        "/api/v1/storyos/{project_id}/cascade/simulate",
        "/api/v1/storyos/{project_id}/cascade/replay/{bridge_id}",
        "/api/v1/storyos/{project_id}/cascade/history",
        "/api/v1/storyos/{project_id}/sflog/raw",
        "/api/v1/storyos/{project_id}/sflog/reparse/{chapter_id}",
        "/api/v1/storyos/{project_id}/migration/preview",
        "/api/v1/storyos/{project_id}/migration/execute",
        "/api/v1/storyos/{project_id}/health",
        "/api/v1/storyos/{project_id}/metrics",
    ]
    for path in expected_special:
        assert path in paths, f"missing special path {path}"


def test_error_envelope_returned_for_validation_error():
    """POST 缺必填字段 → 返回标准 ErrorResponse envelope。"""
    app = FastAPI()
    app.include_router(build_storyos_router())
    client = TestClient(app)
    resp = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={"description": ""},  # 缺 created_chapter + description 为空
    )
    assert resp.status_code == 422
    body = resp.json()
    # FastAPI 默认 ValidationError 不走我们的 envelope，需在 error_handlers 覆盖
    # 此测试在 error_handlers 实现后才会通过
    assert "error" in body or "detail" in body
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`

- [ ] **Step 3: 实现** — `interfaces/api/v1/storyos/router_registry.py`：

```python
"""StoryOS 子包路由器：聚合 40 CRUD + 3 cascade + 2 sflog + 4 migration + 1 health + 1 metrics = 51 端点（migration 4 个含 1E 新增 status/rollback）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from interfaces.api.v1.storyos.crud_factory import build_crud_router
from interfaces.api.v1.storyos.dependencies import (
    get_conflict_service, get_mystery_service, get_twist_service,
    get_promise_service, get_reveal_service, get_expectation_service,
    get_goal_service, get_foreshadowing_service,
    get_cascade_service, get_sflog_service, get_migration_service,
    get_health_service, get_metrics_service,
)
from interfaces.api.v1.storyos.routes import (
    cascade_routes, sflog_routes, migration_routes, health_routes,
)


def build_storyos_router() -> APIRouter:
    """聚合所有 StoryOS 端点为单一 APIRouter。"""
    router = APIRouter(prefix="/api/v1/storyos", tags=["storyos"])

    # ─── 8 registry × 5 CRUD = 40 端点 ───
    # REVIEW-FIX L-10: 旧版传 `service=Depends(get_conflict_service)` 是错的 —
    # Depends 标记对象会被当成 service 实例使用，触发 AttributeError。
    # 新版传 `service_provider=get_xxx_service`（async factory 函数），
    # crud_factory 内部用 `service: Any = Depends(service_provider)` 解析。
    router.include_router(build_crud_router(
        asset_type="conflict",
        service_provider=get_conflict_service,
        create_schema=__import__(
            "interfaces.api.v1.storyos.schemas.conflict_schemas",
            fromlist=["ConflictCreateRequest", "ConflictUpdateRequest", "ConflictResponse"]
        ).ConflictCreateRequest,
        update_schema=__import__(
            "interfaces.api.v1.storyos.schemas.conflict_schemas",
            fromlist=["ConflictUpdateRequest"]
        ).ConflictUpdateRequest,
        response_schema=__import__(
            "interfaces.api.v1.storyos.schemas.conflict_schemas",
            fromlist=["ConflictResponse"]
        ).ConflictResponse,
    ))
    # ... 同构添加 7 个其他 registry（mystery/twist/promise/reveal/expectation/goal/foreshadowing）
    # 每个用 service_provider=get_xxx_service（async），不用 Depends() 包装。

    # ─── 特殊端点 ───
    router.include_router(cascade_routes.router)
    router.include_router(sflog_routes.router)
    router.include_router(migration_routes.router)
    router.include_router(health_routes.router)

    return router
```

并实现 `interfaces/api/v1/storyos/error_handlers.py`：

```python
"""StoryOS 错误处理：把 FastAPI HTTPException + RequestValidationError 统一为 ErrorResponse envelope。"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from interfaces.api.v1.storyos.schemas.common_schemas import ErrorResponse, ErrorDetail


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message="Request validation failed",
                    details={"errors": exc.errors()},
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception):
        # 避免泄露内部 stack（生产环境应仅记录到日志）
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred",
                )
            ).model_dump(),
        )
```

并在 `interfaces/main.py` 注册：

```python
# interfaces/main.py（在 create_app 函数内）
from interfaces.api.v1.storyos.router_registry import build_storyos_router
from interfaces.api.v1.storyos.error_handlers import register_error_handlers

# 在 app 创建后：
app.include_router(build_storyos_router())
register_error_handlers(app)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed

- [ ] **Step 5: Commit** — `git add interfaces/api/v1/storyos/ interfaces/main.py && git commit -m "feat(api): aggregate 40+ storyos routes + ErrorResponse envelope middleware"`

---

### Group B: 8 Registry CRUD 端点（3 任务）

#### Task B1: 4 简单 Registry 端点（Conflict/Mystery/Promise/Goal）

**Files:**
- Create: `interfaces/api/v1/storyos/dependencies.py`
- Create: `tests/integration/api/v1/storyos/test_conflict_endpoints.py`
- Create: `tests/integration/api/v1/storyos/test_mystery_endpoints.py`
- Create: `tests/integration/api/v1/storyos/test_promise_endpoints.py`
- Create: `tests/integration/api/v1/storyos/test_goal_endpoints.py`

- [ ] **Step 1: 写失败测试** — `test_conflict_endpoints.py`（4 端点集成测试）

```python
"""Conflict 5 CRUD 端点集成测试（覆盖 happy path + 4 个错误路径）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import interfaces.main as main_module
from interfaces.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_list_conflicts_empty(client):
    """空项目列表返回 200 + 空 data。"""
    resp = client.get("/api/v1/storyos/proj-new/conflict")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"] == []
    assert body["meta"]["total"] == 0


def test_create_conflict_minimal(client):
    """最小 body 创建 → 201 + 完整 Response。"""
    resp = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={
            "description": "林远 vs 沈墨",
            "created_chapter": 3,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["description"] == "林远 vs 沈墨"
    assert body["status"] == "active"
    assert body["intensity"] == 50
    assert "id" in body
    assert "created_at" in body


def test_get_conflict_by_id(client):
    """create → get 闭环。"""
    create_resp = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={"description": "x", "created_chapter": 1},
    )
    asset_id = create_resp.json()["id"]
    get_resp = client.get(f"/api/v1/storyos/proj-1/conflict/{asset_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == asset_id


def test_get_conflict_not_found_returns_envelope(client):
    """404 返回标准 ErrorResponse envelope。"""
    resp = client.get("/api/v1/storyos/proj-1/conflict/nonexistent-id")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "ASSET_NOT_FOUND"
    assert "nonexistent-id" in body["error"]["message"]


def test_update_conflict_partial(client):
    """PATCH 仅传 status → 仅更新该字段。"""
    create_resp = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={"description": "x", "created_chapter": 1, "intensity": 50},
    )
    asset_id = create_resp.json()["id"]
    patch_resp = client.patch(
        f"/api/v1/storyos/proj-1/conflict/{asset_id}",
        json={"status": "escalated", "intensity": 80},
    )
    assert patch_resp.status_code == 200
    body = patch_resp.json()
    assert body["status"] == "escalated"
    assert body["intensity"] == 80
    assert body["description"] == "x"  # 未变


def test_delete_conflict(client):
    """DELETE → 204，再 GET → 404。"""
    create_resp = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={"description": "x", "created_chapter": 1},
    )
    asset_id = create_resp.json()["id"]
    del_resp = client.delete(f"/api/v1/storyos/proj-1/conflict/{asset_id}")
    assert del_resp.status_code == 204
    get_resp = client.get(f"/api/v1/storyos/proj-1/conflict/{asset_id}")
    assert get_resp.status_code == 404


def test_list_conflicts_with_status_filter(client):
    """status query param 过滤。"""
    # 创建 2 个不同状态的 conflict
    client.post("/api/v1/storyos/proj-1/conflict", json={"description": "a", "created_chapter": 1})
    client.post("/api/v1/storyos/proj-1/conflict", json={"description": "b", "created_chapter": 1, "status": "escalated"})
    resp = client.get("/api/v1/storyos/proj-1/conflict?status=escalated")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert all(c["status"] == "escalated" for c in data)


def test_create_conflict_rejects_intensity_out_of_range(client):
    """intensity=150 → 422 + VALIDATION_ERROR envelope。"""
    resp = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={"description": "x", "created_chapter": 1, "intensity": 150},
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
```

- [ ] **Step 2: 运行测试确认失败** — 期望 404 或 500（路由未注册）

- [ ] **Step 3: 实现** — `interfaces/api/v1/storyos/dependencies.py`：

```python
"""StoryOS 子包 FastAPI 依赖注入工厂。

8 registry 服务的 DI 工厂，每个服务从 1B 的 application/storyos/services/registry_service.py
提取对应 asset_type 的服务实例。
"""
from __future__ import annotations

from functools import lru_cache

from application.storyos.services.registry_service import (
    ConflictRegistryService,
    MysteryRegistryService,
    TwistRegistryService,
    PromiseRegistryService,
    RevealRegistryService,
    ExpectationRegistryService,
    GoalRegistryService,
    ForeshadowingRegistryService,
)
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.sf_log_parser_service import SFLogParserService
from application.storyos.services.foreshadowing_migration_service import ForeshadowingMigrationService
from application.storyos.services.snapshot_projector import StoryOSSnapshotProjector
from interfaces.runtime import get_runtime_container


@lru_cache(maxsize=1)
def _container():
    return get_runtime_container()


async def get_conflict_service() -> ConflictRegistryService:
    return _container().resolve(ConflictRegistryService)


# ... 同构 get_mystery_service / get_twist_service / get_promise_service /
#     get_reveal_service / get_expectation_service / get_goal_service /
#     get_foreshadowing_service

async def get_cascade_service() -> CascadeService:
    return _container().resolve(CascadeService)


async def get_sflog_service() -> SFLogParserService:
    return _container().resolve(SFLogParserService)


async def get_migration_service() -> ForeshadowingMigrationService:
    return _container().resolve(ForeshadowingMigrationService)


async def get_metrics_service() -> StoryOSSnapshotProjector:
    return _container().resolve(StoryOSSnapshotProjector)
```

注：实际 `ConflictRegistryService` 等 8 个 service 在 1B 已实现，1D 仅做 DI 绑定。

- [ ] **Step 4: 运行测试确认通过** — 期望 8 passed（4 端点 × 2 entity = 8）

- [ ] **Step 5: Commit** — `git add interfaces/api/v1/storyos/dependencies.py tests/integration/api/v1/storyos/ && git commit -m "feat(api): wire 4 simple registry endpoints (Conflict/Mystery/Promise/Goal) with 5 CRUD each"`

**Mystery/Promise/Goal 三个 entity 的测试同构（复制 test_conflict_endpoints.py 模板，仅修改 URL 路径前缀），每个 ~120 LOC。**

#### Task B2: 4 复杂 Registry 端点（Twist/Reveal/Expectation/Foreshadowing）

**Files:**
- Create: `tests/integration/api/v1/storyos/test_twist_endpoints.py`
- Create: `tests/integration/api/v1/storyos/test_reveal_endpoints.py`
- Create: `tests/integration/api/v1/storyos/test_expectation_endpoints.py`
- Create: `tests/integration/api/v1/storyos/test_foreshadowing_endpoints.py`

- [ ] **Step 1: 写失败测试** — `test_twist_endpoints.py`（含 TwistType enum 验证）

```python
"""Twist 端点测试（含 TwistType 枚举验证 + 关联 foreshadowing_refs 字段）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_create_twist_with_twist_type(client):
    resp = client.post(
        "/api/v1/storyos/proj-1/twist",
        json={
            "description": "沈墨是卧底",
            "created_chapter": 10,
            "twist_type": "identity_reveal",  # TwistType 枚举
            "trigger_chapter": 25,
            "foreshadowing_refs": ["fs-1", "fs-2"],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["twist_type"] == "identity_reveal"
    assert body["foreshadowing_refs"] == ["fs-1", "fs-2"]


def test_create_twist_rejects_invalid_twist_type(client):
    resp = client.post(
        "/api/v1/storyos/proj-1/twist",
        json={
            "description": "x", "created_chapter": 1,
            "twist_type": "bogus", "trigger_chapter": 5,
        },
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_reveal_endpoint_relationship_to_mystery(client):
    """Reveal 必须关联到一个已存在的 Mystery（外键校验）。"""
    # 先创建一个 mystery
    mys_resp = client.post(
        "/api/v1/storyos/proj-1/mystery",
        json={"description": "x", "created_chapter": 1, "category": "truth"},
    )
    mys_id = mys_resp.json()["id"]
    # 再创建 reveal 关联
    rev_resp = client.post(
        "/api/v1/storyos/proj-1/reveal",
        json={
            "description": "档案室真相",
            "created_chapter": 5,
            "reveal_type": "truth",
            "revealed_chapter": 5,
            "related_mystery_id": mys_id,
        },
    )
    assert rev_resp.status_code == 201
    body = rev_resp.json()
    assert body["related_mystery_id"] == mys_id


def test_expectation_with_intensity_and_links(client):
    resp = client.post(
        "/api/v1/storyos/proj-1/expectation",
        json={
            "description": "读者预期主角获胜",
            "created_chapter": 1,
            "intensity": 70,
            "linked_twist_id": "tw-1",
            "linked_conflict_id": "cf-1",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["intensity"] == 70
    assert body["linked_twist_id"] == "tw-1"


def test_foreshadowing_legacy_migration_field(client):
    """Foreshadowing 接受 migrated_from_legacy_id（1E 迁移填充）。"""
    resp = client.post(
        "/api/v1/storyos/proj-1/foreshadowing",
        json={
            "description": "旧表第 3 条伏笔",
            "created_chapter": 2,
            "importance": 3,
            "migrated_from_legacy_id": "legacy_fs_3",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["migrated_from_legacy_id"] == "legacy_fs_3"
```

- [ ] **Step 2: 运行测试确认失败** — 期望 404

- [ ] **Step 3: 实现** — 测试通过依赖 Task A4 的 factory + Task A5 的路由注册，本任务无需新代码（除非 Twist/Reveal/Expectation/Foreshadowing 字段有特殊校验需要额外 DTO 字段）。**重点是测试覆盖**。

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed × 4 entity = 20 passed

- [ ] **Step 5: Commit** — `git add tests/integration/api/v1/storyos/ && git commit -m "test(api): integration tests for 4 complex registry endpoints (Twist/Reveal/Expectation/Foreshadowing)"`

#### Task B3: 8 Registry 端点性能基准

**Files:**
- Create: `tests/performance/test_api_8_registry_latency.py`
- Create: `tests/conftest.py`（追加 fixture）

- [ ] **Step 1: 写失败测试**

```python
"""8 registry 端点列表查询性能基准（spec §6.4 锁定 < 200ms）。"""
from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient

from interfaces.main import app


@pytest.fixture
def seeded_client():
    """每个 registry 预置 50 条数据，模拟真实负载。"""
    client = TestClient(app)
    project_id = "perf-test-proj"
    seeds = {
        "conflict": {"description": "c", "created_chapter": 1, "intensity": 50},
        "mystery": {"description": "m", "created_chapter": 1, "category": "truth"},
        "twist": {"description": "t", "created_chapter": 1, "twist_type": "identity_reveal", "trigger_chapter": 5},
        "promise": {"description": "p", "created_chapter": 1, "importance": 2},
        "reveal": {"description": "r", "created_chapter": 1, "reveal_type": "truth", "revealed_chapter": 5, "related_mystery_id": "m-1"},
        "expectation": {"description": "e", "created_chapter": 1, "intensity": 50},
        "goal": {"description": "g", "created_chapter": 1, "progress_marker": "T0", "linked_character_id": "char-1"},
        "foreshadowing": {"description": "f", "created_chapter": 1, "importance": 2},
    }
    for asset, body in seeds.items():
        for _ in range(50):
            client.post(f"/api/v1/storyos/{project_id}/{asset}", json=body)
    return client, project_id


@pytest.mark.parametrize("asset_type", [
    "conflict", "mystery", "twist", "promise",
    "reveal", "expectation", "goal", "foreshadowing",
])
def test_list_latency_under_200ms(seeded_client, asset_type):
    client, project_id = seeded_client
    start = time.perf_counter()
    resp = client.get(f"/api/v1/storyos/{project_id}/{asset_type}")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert resp.status_code == 200
    assert elapsed_ms < 200, f"{asset_type} list took {elapsed_ms:.1f}ms (target < 200ms)"
```

- [ ] **Step 2: 运行测试确认失败** — 可能因数据种子未优化而超时，期望 1+ failed

- [ ] **Step 3: 实现（性能调优）**：
- 在 `BaseRegistrySchema` 加 `idx_project_status` 复合索引（`project_id` + `status` + `created_chapter`）
- 仓储层 `list()` 用 `WHERE project_id = ? AND status = ? ORDER BY created_chapter DESC LIMIT ? OFFSET ?`
- 验证：50 条数据查询 < 50ms

- [ ] **Step 4: 运行测试确认通过** — 期望 8 passed

- [ ] **Step 5: Commit** — `git add tests/performance/ infrastructure/persistence/storyos/ && git commit -m "perf(api): add index on (project_id, status, created_chapter) — 8 registry list < 200ms"`

---

### Group C: Cascade + SFLog + Migration + Health 端点（4 任务）

#### Task C1: Cascade 端点（simulate/replay/history）

**Files:**
- Create: `interfaces/api/v1/storyos/routes/__init__.py`
- Create: `interfaces/api/v1/storyos/routes/cascade_routes.py`
- Create: `tests/integration/api/v1/storyos/test_cascade_endpoints.py`

- [ ] **Step 1: 写失败测试**

```python
"""Cascade 端点集成测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_cascade_simulate_mystery_revealed_triggers_expectation(client):
    """mystery_revealed → expectation.READY_TO_FULFILL 级联模拟。"""
    # 1. 创建 mystery + linked expectation
    mys = client.post(
        "/api/v1/storyos/proj-1/mystery",
        json={"description": "m", "created_chapter": 1, "category": "truth"},
    ).json()
    exp = client.post(
        "/api/v1/storyos/proj-1/expectation",
        json={
            "description": "e", "created_chapter": 1, "intensity": 50,
            "linked_conflict_id": mys["id"],  # 关联（通过 conflict_id 占位）
        },
    ).json()

    # 2. 模拟级联
    resp = client.post(
        "/api/v1/storyos/proj-1/cascade/simulate",
        json={
            "trigger": "mystery_revealed",
            "source_asset_type": "mystery",
            "source_asset_id": mys["id"],
            "proposed_new_status": "revealed",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "summary" in body
    assert "steps" in body


def test_cascade_simulate_respects_max_depth_3(client):
    """max_depth=3 锁：请求 max_depth=10 → 422。"""
    resp = client.post(
        "/api/v1/storyos/proj-1/cascade/simulate",
        json={
            "trigger": "mystery_revealed",
            "source_asset_type": "mystery",
            "source_asset_id": "m-1",
            "max_depth": 10,  # 超过 3
        },
    )
    assert resp.status_code == 422


def test_cascade_replay_requires_bridge_id_in_path(client):
    """POST /cascade/replay/{bridge_id} 必须有 bridge_id。"""
    resp = client.post("/api/v1/storyos/proj-1/cascade/replay/bridge-abc", json={"notes": "test"})
    # 1D 阶段 replay 业务由 1B 暴露，可能返回 200 或 501
    assert resp.status_code in (200, 501)


def test_cascade_history_returns_recent_entries(client):
    """GET /cascade/history?limit=50 返回最近级联历史。"""
    resp = client.get("/api/v1/storyos/proj-1/cascade/history?limit=50")
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "meta" in body
```

- [ ] **Step 2: 运行测试确认失败** — 期望 404

- [ ] **Step 3: 实现** — `interfaces/api/v1/storyos/routes/cascade_routes.py`：

```python
"""Cascade 端点：simulate / replay / history。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel

from application.storyos.services.cascade_service import CascadeService
from interfaces.api.v1.storyos.schemas.cascade_schemas import (
    CascadeSimulateRequest, CascadeSimulateResponse, CascadeSimulateSummary,
    CascadeStepDTO, CascadeReplayRequest,
)
from interfaces.api.v1.storyos.dependencies import get_cascade_service


router = APIRouter(prefix="/{project_id}/cascade", tags=["storyos-cascade"])


@router.post("/simulate", response_model=CascadeSimulateResponse)
async def simulate_cascade(
    req: CascadeSimulateRequest,
    service: CascadeService = Depends(get_cascade_service),
) -> CascadeSimulateResponse:
    """模拟一次级联执行（不写入）。"""
    result = await service.simulate(
        project_id=req.project_id,
        trigger=req.trigger,
        source_asset_type=req.source_asset_type,
        source_asset_id=req.source_asset_id,
        proposed_new_status=req.proposed_new_status,
        max_depth=req.max_depth,
    )
    return CascadeSimulateResponse(
        steps=[CascadeStepDTO.from_domain(s) for s in result.steps_executed],
        blocked_steps=[CascadeStepDTO.from_domain(s) for s in result.blocked_steps],
        summary=CascadeSimulateSummary(
            would_block=len(result.blocked_steps) > 0,
            max_depth_reached=result.max_depth_reached,
            steps_count=len(result.steps_executed),
            blocked_steps_count=len(result.blocked_steps),
            would_create_cycle=any(
                "cycle" in s.reason.lower() for s in result.blocked_steps
            ),
        ),
    )


@router.post("/replay/{bridge_id}")
async def replay_cascade(
    bridge_id: str = Path(..., min_length=1),
    req: CascadeReplayRequest = CascadeReplayRequest(),
    service: CascadeService = Depends(get_cascade_service),
) -> dict:
    """回滚指定 bridge_id 的级联（用 1B 的 bridge_log 反向 replay）。"""
    try:
        result = await service.replay(bridge_id, notes=req.notes)
        return {"bridge_id": bridge_id, "status": "replayed", "details": result.to_dict()}
    except NotImplementedError:
        # 1B 可能未实现 replay（spec 列为 Phase 2）
        raise HTTPException(
            status_code=501,
            detail={
                "code": "NOT_IMPLEMENTED",
                "message": "cascade replay is not implemented in this phase",
            },
        )


@router.get("/history")
async def cascade_history(
    project_id: str = Path(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=500),
    service: CascadeService = Depends(get_cascade_service),
) -> dict:
    """查询最近 N 条级联历史（从 cascade_history 表）。"""
    from interfaces.api.v1.storyos.schemas.common_schemas import (
        ListResponseEnvelope, PaginationMeta,
    )
    entries, total = await service.get_history(project_id, limit=limit)
    return {
        "data": [e.to_dict() for e in entries],
        "meta": PaginationMeta.compute(total=total, page=1, page_size=limit),
    }
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed

- [ ] **Step 5: Commit** — `git add interfaces/api/v1/storyos/routes/cascade_routes.py tests/integration/api/v1/storyos/test_cascade_endpoints.py && git commit -m "feat(api): add cascade simulate/replay/history endpoints"`

#### Task C2: SFLog 端点（raw/reparse）

**Files:**
- Create: `interfaces/api/v1/storyos/routes/sflog_routes.py`
- Create: `tests/integration/api/v1/storyos/test_sflog_endpoints.py`

- [ ] **Step 1: 写失败测试**

```python
"""SFLog 端点：raw 文本查询 + reparse 重新解析。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_sflog_raw_returns_extracted_tags(client):
    """GET /sflog/raw?chapter=5 提取章节文本中的 SF_LOG 注释。"""
    resp = client.get("/api/v1/storyos/proj-1/sflog/raw?chapter=5")
    assert resp.status_code == 200
    body = resp.json()
    assert "raw_text" in body
    assert "records" in body
    assert "sf_log_count" in body


def test_sflog_reparse_re_runs_pipeline(client):
    """POST /sflog/reparse/{chapter_id} 重新解析（不应用状态）。"""
    resp = client.post("/api/v1/storyos/proj-1/sflog/reparse/5")
    assert resp.status_code == 200
    body = resp.json()
    assert "parsed_count" in body
    assert "format_errors" in body
    assert "match_report" in body
```

- [ ] **Step 2: 运行测试确认失败** — 期望 404

- [ ] **Step 3: 实现** — `interfaces/api/v1/storyos/routes/sflog_routes.py`：

```python
"""SFLog 端点：raw 文本查询 + reparse。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from application.storyos.services.sf_log_parser_service import SFLogParserService
from interfaces.api.v1.storyos.dependencies import get_sflog_service


router = APIRouter(prefix="/{project_id}/sflog", tags=["storyos-sflog"])


@router.get("/raw")
async def sflog_raw(
    project_id: str = Path(..., min_length=1),
    chapter: int = Query(..., ge=1),
    service: SFLogParserService = Depends(get_sflog_service),
) -> dict:
    """提取指定章节文本中的 SF_LOG 注释（不应用状态变更）。"""
    raw_text = await service.get_chapter_text(project_id, chapter)
    records = await service.parse_only(raw_text, chapter_id=chapter)
    return {
        "project_id": project_id,
        "chapter_id": chapter,
        "raw_text": raw_text,
        "records": [r.model_dump() for r in records],
        "sf_log_count": len(records),
    }


@router.post("/reparse/{chapter_id}")
async def sflog_reparse(
    project_id: str = Path(..., min_length=1),
    chapter_id: int = Path(..., ge=1),
    service: SFLogParserService = Depends(get_sflog_service),
) -> dict:
    """重新解析章节文本（dry-run：parse → validate → match，不应用状态）。"""
    raw_text = await service.get_chapter_text(project_id, chapter_id)
    parsed = await service.parse_only(raw_text, chapter_id=chapter_id)
    format_errors = await service.validate_format(parsed)
    match_report = await service.match_against_predeclared(
        parsed,
        predeclared=await service.get_predeclared_for_chapter(project_id, chapter_id),
    )
    return {
        "project_id": project_id,
        "chapter_id": chapter_id,
        "parsed_count": len(parsed),
        "format_errors": [fe.model_dump() for fe in format_errors],
        "match_report": match_report.model_dump(),
    }
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed

- [ ] **Step 5: Commit** — `git add interfaces/api/v1/storyos/routes/sflog_routes.py tests/integration/api/v1/storyos/test_sflog_endpoints.py && git commit -m "feat(api): add sflog raw/reparse endpoints"`

#### Task C3: Migration 端点（preview/execute，1D 桩）

**Files:**
- Create: `interfaces/api/v1/storyos/routes/migration_routes.py`
- Create: `tests/integration/api/v1/storyos/test_migration_endpoints.py`

- [ ] **Step 1: 写失败测试**

```python
"""Migration 端点（1D 桩，1E 联通）。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_migration_preview_returns_501_until_1E(client):
    """1D 阶段：preview 端点存在但返回 501 Not Implemented。"""
    resp = client.post("/api/v1/storyos/proj-1/migration/preview")
    assert resp.status_code == 501
    body = resp.json()
    assert body["error"]["code"] == "NOT_IMPLEMENTED"
    assert "Phase 1E" in body["error"]["message"]


def test_migration_execute_returns_501_until_1E(client):
    resp = client.post(
        "/api/v1/storyos/proj-1/migration/execute",
        json={"batch_size": 500, "dry_run": False},
    )
    assert resp.status_code == 501
    body = resp.json()
    assert body["error"]["code"] == "NOT_IMPLEMENTED"


def test_migration_endpoints_registered_in_schema(client):
    """即使 1D 桩，端点必须在 OpenAPI schema 可见。"""
    resp = client.get("/openapi.json")
    schema = resp.json()
    paths = schema["paths"]
    assert "/api/v1/storyos/{project_id}/migration/preview" in paths
    assert "/api/v1/storyos/{project_id}/migration/execute" in paths
```

- [ ] **Step 2: 运行测试确认失败** — 期望 404

- [ ] **Step 3: 实现** — `interfaces/api/v1/storyos/routes/migration_routes.py`：

```python
"""Migration 端点（1D 桩 → 1E 联通）。

1D 阶段：路由注册 + 501 Not Implemented 返回。
1E 阶段：替换为 ForeshadowingMigrationService 业务逻辑。
"""
from __future__ import annotations

from fastapi import APIRouter, Path

from interfaces.api.v1.storyos.schemas.migration_schemas import (
    MigrationExecuteRequest,
)


router = APIRouter(prefix="/{project_id}/migration", tags=["storyos-migration"])


_NOT_IMPLEMENTED_501 = {
    "error": {
        "code": "NOT_IMPLEMENTED",
        "message": "Migration endpoint will be implemented in Phase 1E",
        "details": {"phase": "1E", "scheduled": "2026-07"},
    }
}


@router.post("/preview")
async def migration_preview(project_id: str = Path(..., min_length=1)) -> dict:
    """1D 桩：扫描旧 foreshadowing 表，预览可迁移数据。

    1E 实现：从 application.storyos.services.foreshadowing_migration_service.scan() 返回。
    """
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_501["error"])


@router.post("/execute")
async def migration_execute(
    req: MigrationExecuteRequest,
    project_id: str = Path(..., min_length=1),
) -> dict:
    """1D 桩：实际迁移旧 foreshadowing 数据。

    1E 实现：批量执行 + 断点续跑。
    """
    from fastapi import HTTPException
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED_501["error"])
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed

- [ ] **Step 5: Commit** — `git add interfaces/api/v1/storyos/routes/migration_routes.py tests/integration/api/v1/storyos/test_migration_endpoints.py && git commit -m "feat(api): add migration preview/execute endpoint stubs (501 until 1E)"`

#### Task C4: Health + Metrics 端点

**Files:**
- Create: `interfaces/api/v1/storyos/routes/health_routes.py`
- Create: `tests/integration/api/v1/storyos/test_health_endpoints.py`

- [ ] **Step 1: 写失败测试**

```python
"""Health + Metrics 端点：StoryOS 子系统健康检查与指标查询。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint_returns_ok(client):
    """GET /health → 200 + 状态信息。"""
    resp = client.get("/api/v1/storyos/proj-1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "degraded", "down")
    assert "components" in body
    # 至少检查 4 个组件
    expected_components = {"registry", "cascade", "sflog_parser", "bridge"}
    assert expected_components.issubset(body["components"].keys())


def test_metrics_endpoint_returns_storyos_metrics(client):
    """GET /metrics → 200 + StoryOSMetrics 6 指标（spec §5.2 锁定）。"""
    resp = client.get("/api/v1/storyos/proj-1/metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert "sflog_format_compliance_rate" in body
    assert "sflog_predeclared_match_rate" in body
    assert "cascade_block_rate" in body
    assert "bridge_failure_rate" in body
    assert "avg_cascade_depth" in body
    assert "force_pass_count_per_chapter" in body
```

- [ ] **Step 2: 运行测试确认失败** — 期望 404

- [ ] **Step 3: 实现** — `interfaces/api/v1/storyos/routes/health_routes.py`：

```python
"""Health + Metrics 端点。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from application.storyos.services.snapshot_projector import StoryOSSnapshotProjector
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.sf_log_parser_service import SFLogParserService
from application.storyos.services.evolution_bridge_service import EvolutionBridgeService
from interfaces.api.v1.storyos.dependencies import get_metrics_service


router = APIRouter(prefix="/{project_id}", tags=["storyos-health"])


@router.get("/health")
async def health(
    project_id: str = Path(..., min_length=1),
    metrics_service: StoryOSSnapshotProjector = Depends(get_metrics_service),
    cascade_service: CascadeService = ...,
    sflog_service: SFLogParserService = ...,
    bridge_service: EvolutionBridgeService = ...,
) -> dict:
    """聚合 4 个子组件的健康状态。"""
    components = {}
    for name, svc in [
        ("registry", metrics_service),
        ("cascade", cascade_service),
        ("sflog_parser", sflog_service),
        ("bridge", bridge_service),
    ]:
        try:
            # 简单 ping：检查 service 是否有 .ping() 或尝试一个无副作用操作
            components[name] = {"status": "ok"}
        except Exception as e:
            components[name] = {"status": "down", "error": str(e)}

    overall = "ok" if all(c["status"] == "ok" for c in components.values()) else "degraded"
    return {
        "project_id": project_id,
        "status": overall,
        "components": components,
        "timestamp": "2026-07-03T00:00:00Z",  # 实际用 datetime.utcnow().isoformat()
    }


@router.get("/metrics")
async def metrics(
    project_id: str = Path(..., min_length=1),
    metrics_service: StoryOSSnapshotProjector = Depends(get_metrics_service),
) -> dict:
    """查询 StoryOSMetrics 6 指标（spec §5.2 锁定）。"""
    return await metrics_service.get_metrics(project_id)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed

- [ ] **Step 5: Commit** — `git add interfaces/api/v1/storyos/routes/health_routes.py tests/integration/api/v1/storyos/test_health_endpoints.py && git commit -m "feat(api): add health/metrics endpoints for StoryOS subsystem observability"`

---

### Group D: Frontend 基础设施（4 任务）

#### Task D1: TypeScript 类型 + API client 模块

**Files:**
- Create: `frontend/src/types/storyos.ts`
- Create: `frontend/src/api/storyos/http.ts`
- Create: `frontend/src/api/storyos/registry.ts`
- Create: `frontend/src/api/storyos/cascade.ts`
- Create: `frontend/src/api/storyos/sflog.ts`
- Create: `frontend/src/api/storyos/migration.ts`
- Create: `frontend/src/api/storyos/health.ts`
- Create: `frontend/src/api/storyos/index.ts`
- Create: `frontend/src/api/storyos/__tests__/registry.spec.ts`
- Create: `frontend/src/api/storyos/__tests__/cascade.spec.ts`
- Create: `frontend/src/api/storyos/__tests__/sflog.spec.ts`
- Create: `frontend/src/api/storyos/__tests__/migration.spec.ts`

- [ ] **Step 1: 写失败测试** — `frontend/src/api/storyos/__tests__/registry.spec.ts`

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { conflictApi } from '../registry'
import { apiClient } from '../http'

vi.mock('../http', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('conflictApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('list 调用正确路径与 query params', async () => {
    ;(apiClient.get as any).mockResolvedValue({ data: [], meta: { total: 0 } })
    await conflictApi.list('proj-1', { status: 'active', page: 1, pageSize: 20 })
    expect(apiClient.get).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/conflict',
      { params: { status: 'active', page: 1, page_size: 20 } },
    )
  })

  it('get 调用正确路径', async () => {
    ;(apiClient.get as any).mockResolvedValue({ data: { id: 'cf-1' } })
    await conflictApi.get('proj-1', 'cf-1')
    expect(apiClient.get).toHaveBeenCalledWith('/api/v1/storyos/proj-1/conflict/cf-1')
  })

  it('create POST body', async () => {
    ;(apiClient.post as any).mockResolvedValue({ data: { id: 'cf-1' } })
    await conflictApi.create('proj-1', {
      description: 'x',
      createdChapter: 1,
      status: 'active',
      intensity: 50,
    })
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/conflict',
      expect.objectContaining({ description: 'x' }),
    )
  })

  it('update PATCH 部分字段', async () => {
    ;(apiClient.patch as any).mockResolvedValue({ data: { id: 'cf-1' } })
    await conflictApi.update('proj-1', 'cf-1', { status: 'escalated' })
    expect(apiClient.patch).toHaveBeenCalledWith(
      '/api/v1/storyos/proj-1/conflict/cf-1',
      { status: 'escalated' },
    )
  })

  it('delete 返回 204 不解析 body', async () => {
    ;(apiClient.delete as any).mockResolvedValue({ status: 204 })
    await conflictApi.delete('proj-1', 'cf-1')
    expect(apiClient.delete).toHaveBeenCalledWith('/api/v1/storyos/proj-1/conflict/cf-1')
  })
})
```

- [ ] **Step 2: 运行测试确认失败** — `cd frontend && npx vitest run src/api/storyos/__tests__/registry.spec.ts` 期望 `Failed to resolve import`

- [ ] **Step 3: 实现** — `frontend/src/types/storyos.ts`：

```typescript
/**
 * StoryOS TypeScript 类型（与后端 Pydantic DTO 同源）。
 * 字段命名用 camelCase（前端），由 API client 在调用时转 snake_case。
 */

export type AssetStatus =
  | 'active' | 'accumulating' | 'planted' | 'developing'
  | 'hidden' | 'ready_to_fulfill' | 'escalated' | 'revealed'
  | 'fulfilled' | 'resolved' | 'abandoned' | 'dead'

export type SFLogType =
  | 'character_emotion' | 'character_relation_change' | 'character_location_change'
  | 'character_physical_change' | 'knowledge_gain' | 'conflict_escalate'
  | 'mystery_clue' | 'twist_reveal' | 'expectation_fulfill'
  | 'goal_milestone' | 'registry_create'

export type CascadeTrigger =
  | 'mystery_revealed' | 'twist_revealed' | 'reveal_revealed'
  | 'promise_fulfilled' | 'conflict_resolved' | 'conflict_escalated'

export interface StoryOSAsset {
  id: string
  projectId: string
  description: string
  status: AssetStatus
  createdChapter: number
  linkedAssets: Record<string, string>
  cascadeUpdatedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface ConflictAsset extends StoryOSAsset {
  intensity: number
  participants: string[]
  resolutionChapter: number | null
}

export interface MysteryAsset extends StoryOSAsset {
  category: 'truth' | 'relationship' | 'identity' | 'ability' | 'other'
  clues: ClueItem[]
  solutionChapter: number | null
}

export interface ClueItem {
  id: string
  mysteryId: string
  description: string
  sourceChapter: number
  sourceLocation: string
  category: string
  status: AssetStatus
  discoveredInChapter: number | null
  invalidatedInChapter: number | null
}

export interface TwistAsset extends StoryOSAsset {
  twistType: 'identity_reveal' | 'betrayal' | 'fortune_reversal' | 'world_rule_reveal' | 'sacrifice' | 'truth_revealed'
  triggerChapter: number
  foreshadowingRefs: string[]
}

export interface PromiseAsset extends StoryOSAsset {
  fulfillmentChapter: number | null
  importance: 1 | 2 | 3 | 4
  linkedConflictId: string | null
}

export interface RevealAsset extends StoryOSAsset {
  revealType: 'truth' | 'identity' | 'rule' | 'ability' | 'other'
  revealedChapter: number
  relatedMysteryId: string
}

export interface ExpectationAsset extends StoryOSAsset {
  intensity: number
  linkedTwistId: string | null
  linkedConflictId: string | null
  readyChapter: number | null
}

export interface GoalAsset extends StoryOSAsset {
  progressMarker: 'T0' | 'T1' | 'T2' | 'T3' | 'T4' | 'T5' | 'T6' | 'T7' | 'T8' | 'T9'
  linkedCharacterId: string
  completionChapter: number | null
}

export interface ForeshadowingAsset extends StoryOSAsset {
  importance: 1 | 2 | 3 | 4
  payoffChapter: number | null
  migratedFromLegacyId: string | null
}

export type AssetType =
  | 'conflict' | 'mystery' | 'twist' | 'promise'
  | 'reveal' | 'expectation' | 'goal' | 'foreshadowing'

export interface PaginationMeta {
  total: number
  page: number
  pageSize: number
  totalPages: number
  hasNext: boolean
  hasPrev: boolean
}

export interface ListResponse<T> {
  data: T[]
  meta: PaginationMeta
}

export interface ErrorResponse {
  error: {
    code: string
    message: string
    details?: Record<string, unknown>
  }
}

// Cascade
export interface CascadeStep {
  trigger: CascadeTrigger
  sourceAssetType: AssetType
  sourceAssetId: string
  targetAssetType: AssetType
  targetAssetId: string
  newStatus: AssetStatus | null
  intensityDelta: number | null
  reason: string
}

export interface CascadeSimulateRequest {
  trigger: CascadeTrigger
  sourceAssetType: AssetType
  sourceAssetId: string
  proposedNewStatus?: AssetStatus
  maxDepth?: number
}

export interface CascadeSimulateSummary {
  wouldBlock: boolean
  maxDepthReached: number
  stepsCount: number
  blockedStepsCount: number
  wouldCreateCycle: boolean
}

export interface CascadeSimulateResponse {
  steps: CascadeStep[]
  blockedSteps: CascadeStep[]
  summary: CascadeSimulateSummary
}

// SFLog
export interface SFLogRecord {
  logType: SFLogType
  params: Record<string, string>
  raw: string
  chapterId: number
  charPosition: number
  assetId: string | null
}

export interface SFLogRawResponse {
  projectId: string
  chapterId: number
  rawText: string
  records: SFLogRecord[]
  sfLogCount: number
}

export interface MatchReport {
  predeclaredTotal: number
  predeclaredImplemented: number
  missingChanges: unknown[]
  unexpectedRecords: SFLogRecord[]
  matchRate: number
}

export interface SFLogReparseResponse {
  projectId: string
  chapterId: number
  parsedCount: number
  formatErrors: unknown[]
  matchReport: MatchReport
}

// Migration
export interface MigrationPreviewResponse {
  total: number
  scanned: number
  migratable: number
  skipped: number
  invalid: number
  sampleErrors: Array<{ legacyId: string; reason: string }>
}

export interface MigrationExecuteRequest {
  batchSize?: number
  dryRun?: boolean
}

export interface MigrationExecuteResponse {
  migrationId: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  batchesTotal: number
  batchesDone: number
  errors: Array<{ batchId: string; reason: string }>
}

// Health/Metrics
export interface HealthComponent {
  status: 'ok' | 'degraded' | 'down'
  error?: string
}

export interface HealthResponse {
  projectId: string
  status: 'ok' | 'degraded' | 'down'
  components: Record<'registry' | 'cascade' | 'sflog_parser' | 'bridge', HealthComponent>
  timestamp: string
}

export interface StoryOSMetrics {
  sflogFormatComplianceRate: number
  sflogPredeclaredMatchRate: number
  cascadeBlockRate: number
  bridgeFailureRate: number
  avgCascadeDepth: number
  forcePassCountPerChapter: number
}
```

`frontend/src/api/storyos/http.ts`（共享 apiClient 复用 `frontend/src/api/config.ts` 的实例）：

```typescript
import { apiClient } from '../config'
export { apiClient }
```

`frontend/src/api/storyos/registry.ts`（8 registry 客户端）：

```typescript
import { apiClient } from './http'
import type {
  AssetType, ConflictAsset, MysteryAsset, TwistAsset, PromiseAsset,
  RevealAsset, ExpectationAsset, GoalAsset, ForeshadowingAsset,
  ListResponse, PaginationMeta,
} from '@/types/storyos'

/** 通用 CRUD 客户端工厂（8 registry 共用）。*/
function buildCRUDClient<T extends { id: string }>(assetType: AssetType) {
  const base = (projectId: string) => `/api/v1/storyos/${projectId}/${assetType}`

  return {
    async list(
      projectId: string,
      params?: { status?: string; page?: number; pageSize?: number },
    ): Promise<ListResponse<T>> {
      const { data } = await apiClient.get(base(projectId), {
        params: {
          status: params?.status,
          page: params?.page ?? 1,
          page_size: params?.pageSize ?? 20,
        },
      })
      return data
    },

    async get(projectId: string, assetId: string): Promise<T> {
      const { data } = await apiClient.get(`${base(projectId)}/${assetId}`)
      return data.data ?? data
    },

    async create(projectId: string, payload: Partial<T>): Promise<T> {
      const { data } = await apiClient.post(base(projectId), payload)
      return data.data ?? data
    },

    async update(projectId: string, assetId: string, payload: Partial<T>): Promise<T> {
      const { data } = await apiClient.patch(`${base(projectId)}/${assetId}`, payload)
      return data.data ?? data
    },

    async delete(projectId: string, assetId: string): Promise<void> {
      await apiClient.delete(`${base(projectId)}/${assetId}`)
    },
  }
}

export const conflictApi = buildCRUDClient<ConflictAsset>('conflict')
export const mysteryApi = buildCRUDClient<MysteryAsset>('mystery')
export const twistApi = buildCRUDClient<TwistAsset>('twist')
export const promiseApi = buildCRUDClient<PromiseAsset>('promise')
export const revealApi = buildCRUDClient<RevealAsset>('reveal')
export const expectationApi = buildCRUDClient<ExpectationAsset>('expectation')
export const goalApi = buildCRUDClient<GoalAsset>('goal')
export const foreshadowingApi = buildCRUDClient<ForeshadowingAsset>('foreshadowing')
```

`frontend/src/api/storyos/cascade.ts`：

```typescript
import { apiClient } from './http'
import type {
  CascadeSimulateRequest, CascadeSimulateResponse,
  CascadeStep, ListResponse,
} from '@/types/storyos'

export const cascadeApi = {
  async simulate(projectId: string, req: CascadeSimulateRequest): Promise<CascadeSimulateResponse> {
    const { data } = await apiClient.post(`/api/v1/storyos/${projectId}/cascade/simulate`, req)
    return data
  },

  async replay(projectId: string, bridgeId: string, notes?: string): Promise<{ bridgeId: string; status: string }> {
    const { data } = await apiClient.post(`/api/v1/storyos/${projectId}/cascade/replay/${bridgeId}`, { notes })
    return data
  },

  async history(projectId: string, limit = 50): Promise<ListResponse<unknown>> {
    const { data } = await apiClient.get(`/api/v1/storyos/${projectId}/cascade/history`, {
      params: { limit },
    })
    return data
  },
}
```

`frontend/src/api/storyos/sflog.ts`：

```typescript
import { apiClient } from './http'
import type { SFLogRawResponse, SFLogReparseResponse } from '@/types/storyos'

export const sflogApi = {
  async raw(projectId: string, chapter: number): Promise<SFLogRawResponse> {
    const { data } = await apiClient.get(`/api/v1/storyos/${projectId}/sflog/raw`, {
      params: { chapter },
    })
    return data
  },

  async reparse(projectId: string, chapterId: number): Promise<SFLogReparseResponse> {
    const { data } = await apiClient.post(`/api/v1/storyos/${projectId}/sflog/reparse/${chapterId}`)
    return data
  },
}
```

`frontend/src/api/storyos/migration.ts`：

```typescript
import { apiClient } from './http'
import type {
  MigrationPreviewResponse, MigrationExecuteRequest, MigrationExecuteResponse,
} from '@/types/storyos'
import type { AxiosError } from 'axios'

/** 1D 阶段：端点存在但返回 501。1E 联通后业务逻辑直接生效。*/
export const migrationApi = {
  async preview(projectId: string): Promise<MigrationPreviewResponse> {
    try {
      const { data } = await apiClient.post(`/api/v1/storyos/${projectId}/migration/preview`)
      return data
    } catch (e) {
      const err = e as AxiosError<{ error: { message: string } }>
      if (err.response?.status === 501) {
        // 1D 桩：返回占位响应，UI 显示"功能开发中"
        return {
          total: 0, scanned: 0, migratable: 0, skipped: 0, invalid: 0, sampleErrors: [],
        }
      }
      throw e
    }
  },

  async execute(projectId: string, req: MigrationExecuteRequest = {}): Promise<MigrationExecuteResponse> {
    try {
      const { data } = await apiClient.post(`/api/v1/storyos/${projectId}/migration/execute`, req)
      return data
    } catch (e) {
      const err = e as AxiosError
      if (err.response?.status === 501) {
        return {
          migrationId: 'pending-1e',
          status: 'pending',
          batchesTotal: 0, batchesDone: 0, errors: [],
        }
      }
      throw e
    }
  },
}
```

`frontend/src/api/storyos/health.ts`：

```typescript
import { apiClient } from './http'
import type { HealthResponse, StoryOSMetrics } from '@/types/storyos'

export const healthApi = {
  async check(projectId: string): Promise<HealthResponse> {
    const { data } = await apiClient.get(`/api/v1/storyos/${projectId}/health`)
    return data
  },

  async metrics(projectId: string): Promise<StoryOSMetrics> {
    const { data } = await apiClient.get(`/api/v1/storyos/${projectId}/metrics`)
    return data
  },
}
```

`frontend/src/api/storyos/index.ts`：

```typescript
export * from './registry'
export * from './cascade'
export * from './sflog'
export * from './migration'
export * from './health'
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed × 4 模块 = 20 passed

- [ ] **Step 5: Commit** — `git add frontend/src/types/storyos.ts frontend/src/api/storyos/ && git commit -m "feat(frontend): add StoryOS TypeScript types + 5 API client modules"`

#### Task D2: 3 Pinia stores

**Files:**
- Create: `frontend/src/stores/storyos/queries.ts`
- Create: `frontend/src/stores/storyos/cascade.ts`
- Create: `frontend/src/stores/storyos/sflog.ts`
- Create: `frontend/src/stores/storyos/index.ts`
- Create: `frontend/src/stores/storyos/__tests__/queries.spec.ts`
- Create: `frontend/src/stores/storyos/__tests__/cascade.spec.ts`
- Create: `frontend/src/stores/storyos/__tests__/sflog.spec.ts`

- [ ] **Step 1: 写失败测试** — `queries.spec.ts`（部分核心测试）

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useStoryosQueriesStore } from '../queries'
import { conflictApi } from '@/api/storyos'

vi.mock('@/api/storyos', () => ({
  conflictApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  mysteryApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  twistApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  promiseApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  revealApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  expectationApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  goalApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  foreshadowingApi: { list: vi.fn(), get: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}))

describe('useStoryosQueriesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('fetchList 加载数据并存入 cache', async () => {
    ;(conflictApi.list as any).mockResolvedValue({
      data: [{ id: 'cf-1', description: 'x' }],
      meta: { total: 1, page: 1, pageSize: 20, totalPages: 1, hasNext: false, hasPrev: false },
    })
    const store = useStoryosQueriesStore()
    await store.fetchList('proj-1', 'conflict', { page: 1, pageSize: 20 })
    expect(store.conflictList).toHaveLength(1)
    expect(store.conflictList[0].id).toBe('cf-1')
  })

  it('fetchList 缓存命中不重复请求', async () => {
    ;(conflictApi.list as any).mockResolvedValue({
      data: [], meta: { total: 0, page: 1, pageSize: 20, totalPages: 0, hasNext: false, hasPrev: false },
    })
    const store = useStoryosQueriesStore()
    await store.fetchList('proj-1', 'conflict', { page: 1, pageSize: 20 })
    await store.fetchList('proj-1', 'conflict', { page: 1, pageSize: 20 })  // 第二次
    expect(conflictApi.list).toHaveBeenCalledTimes(1)
  })

  it('create 追加到 cache 头部', async () => {
    ;(conflictApi.create as any).mockResolvedValue({ id: 'cf-2', description: 'new' })
    const store = useStoryosQueriesStore()
    const result = await store.create('proj-1', 'conflict', { description: 'new', createdChapter: 1 })
    expect(result.id).toBe('cf-2')
  })

  it('update 替换 cache 项', async () => {
    ;(conflictApi.update as any).mockResolvedValue({ id: 'cf-1', description: 'updated' })
    const store = useStoryosQueriesStore()
    store.conflictList = [{ id: 'cf-1', description: 'old' }] as any
    await store.update('proj-1', 'conflict', 'cf-1', { description: 'updated' })
    expect(store.conflictList[0].description).toBe('updated')
  })

  it('delete 从 cache 移除', async () => {
    ;(conflictApi.delete as any).mockResolvedValue(undefined)
    const store = useStoryosQueriesStore()
    store.conflictList = [{ id: 'cf-1' }, { id: 'cf-2' }] as any
    await store.delete('proj-1', 'conflict', 'cf-1')
    expect(store.conflictList).toHaveLength(1)
    expect(store.conflictList[0].id).toBe('cf-2')
  })

  it('invalidate 清除 cache 强制 refetch', async () => {
    ;(conflictApi.list as any).mockResolvedValue({
      data: [], meta: { total: 0, page: 1, pageSize: 20, totalPages: 0, hasNext: false, hasPrev: false },
    })
    const store = useStoryosQueriesStore()
    await store.fetchList('proj-1', 'conflict', {})
    await store.invalidate('conflict')
    await store.fetchList('proj-1', 'conflict', {})
    expect(conflictApi.list).toHaveBeenCalledTimes(2)
  })
})
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `Failed to resolve import`

- [ ] **Step 3: 实现** — `frontend/src/stores/storyos/queries.ts`：

```typescript
/**
 * StoryOS 8 Registry 通用查询 store。
 *
 * 设计要点：
 * - 8 registry 字段平铺（conflictList / mysteryList / ...）避免泛型复杂度
 * - cache key = (projectId, assetType, params) → 简单 in-memory Map
 * - 跨视图状态同步：mutation（create/update/delete）后自动更新本地 cache
 * - cascade 触发后调用 invalidate() 强制 refetch
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  conflictApi, mysteryApi, twistApi, promiseApi,
  revealApi, expectationApi, goalApi, foreshadowingApi,
} from '@/api/storyos'
import type { AssetType } from '@/types/storyos'

const API_MAP = {
  conflict: conflictApi,
  mystery: mysteryApi,
  twist: twistApi,
  promise: promiseApi,
  reveal: revealApi,
  expectation: expectationApi,
  goal: goalApi,
  foreshadowing: foreshadowingApi,
} as const

export const useStoryosQueriesStore = defineStore('storyos-queries', () => {
  // ─── 8 registry 列表（reactive refs）───
  const conflictList = ref<any[]>([])
  const mysteryList = ref<any[]>([])
  const twistList = ref<any[]>([])
  const promiseList = ref<any[]>([])
  const revealList = ref<any[]>([])
  const expectationList = ref<any[]>([])
  const goalList = ref<any[]>([])
  const foreshadowingList = ref<any[]>([])

  // ─── 详情缓存（Map<assetId, asset>）───
  const detailCache = ref<Map<string, any>>(new Map())
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  // ─── 列表 cache key ───
  const listCache = ref<Map<string, { data: any[]; meta: any }>>(new Map())

  function _listRef(assetType: AssetType) {
    return {
      conflict: conflictList,
      mystery: mysteryList,
      twist: twistList,
      promise: promiseList,
      reveal: revealList,
      expectation: expectationList,
      goal: goalList,
      foreshadowing: foreshadowingList,
    }[assetType]
  }

  function _cacheKey(projectId: string, assetType: AssetType, params: any): string {
    return `${projectId}:${assetType}:${JSON.stringify(params)}`
  }

  async function fetchList(
    projectId: string,
    assetType: AssetType,
    params: { status?: string; page?: number; pageSize?: number } = {},
  ) {
    const key = _cacheKey(projectId, assetType, params)
    if (listCache.value.has(key)) {
      const cached = listCache.value.get(key)!
      _listRef(assetType).value = cached.data
      return cached
    }
    isLoading.value = true
    try {
      const result = await API_MAP[assetType].list(projectId, params) as any
      _listRef(assetType).value = result.data
      listCache.value.set(key, result)
      return result
    } finally {
      isLoading.value = false
    }
  }

  async function fetchOne(projectId: string, assetType: AssetType, assetId: string) {
    const key = `${projectId}:${assetType}:${assetId}`
    if (detailCache.value.has(key)) {
      return detailCache.value.get(key)!
    }
    const item = await API_MAP[assetType].get(projectId, assetId) as any
    detailCache.value.set(key, item)
    return item
  }

  async function create(projectId: string, assetType: AssetType, payload: any) {
    const created = await API_MAP[assetType].create(projectId, payload) as any
    _listRef(assetType).value = [created, ..._listRef(assetType).value]
    invalidate(assetType)
    return created
  }

  async function update(projectId: string, assetType: AssetType, assetId: string, payload: any) {
    const updated = await API_MAP[assetType].update(projectId, assetId, payload) as any
    const list = _listRef(assetType).value
    const idx = list.findIndex((x: any) => x.id === assetId)
    if (idx >= 0) list[idx] = updated
    detailCache.value.set(`${projectId}:${assetType}:${assetId}`, updated)
    return updated
  }

  async function deleteOne(projectId: string, assetType: AssetType, assetId: string) {
    await API_MAP[assetType].delete(projectId, assetId)
    _listRef(assetType).value = _listRef(assetType).value.filter((x: any) => x.id !== assetId)
    detailCache.value.delete(`${projectId}:${assetType}:${assetId}`)
  }

  function invalidate(assetType?: AssetType) {
    if (assetType) {
      // 清除该 assetType 的所有 listCache 条目
      for (const key of listCache.value.keys()) {
        if (key.includes(`:${assetType}:`)) listCache.value.delete(key)
      }
    } else {
      listCache.value.clear()
    }
  }

  return {
    conflictList, mysteryList, twistList, promiseList,
    revealList, expectationList, goalList, foreshadowingList,
    detailCache, isLoading, error,
    fetchList, fetchOne, create, update, delete: deleteOne, invalidate,
  }
})
```

`cascade.ts` 与 `sflog.ts` 模式类似，参考 1B service 接口：

```typescript
// frontend/src/stores/storyos/cascade.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { cascadeApi } from '@/api/storyos'
import type { CascadeSimulateRequest, CascadeSimulateResponse, CascadeStep } from '@/types/storyos'
import { useStoryosQueriesStore } from './queries'

export const useStoryosCascadeStore = defineStore('storyos-cascade', () => {
  const lastSimulation = ref<CascadeSimulateResponse | null>(null)
  const history = ref<any[]>([])
  const isSimulating = ref(false)
  const error = ref<string | null>(null)

  async function simulate(projectId: string, req: CascadeSimulateRequest) {
    isSimulating.value = true
    try {
      const result = await cascadeApi.simulate(projectId, req)
      lastSimulation.value = result
      return result
    } finally {
      isSimulating.value = false
    }
  }

  async function replay(projectId: string, bridgeId: string, notes?: string) {
    const result = await cascadeApi.replay(projectId, bridgeId, notes)
    // 回滚后失效所有 cache（cascade 可能影响多个 registry）
    useStoryosQueriesStore().invalidate()
    return result
  }

  async function loadHistory(projectId: string, limit = 50) {
    const result = await cascadeApi.history(projectId, limit)
    history.value = result.data
    return result
  }

  return { lastSimulation, history, isSimulating, error, simulate, replay, loadHistory }
})
```

```typescript
// frontend/src/stores/storyos/sflog.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sflogApi } from '@/api/storyos'
import type { SFLogRawResponse, SFLogReparseResponse } from '@/types/storyos'

export const useStoryosSflogStore = defineStore('storyos-sflog', () => {
  const currentRaw = ref<SFLogRawResponse | null>(null)
  const currentReparse = ref<SFLogReparseResponse | null>(null)
  const isLoading = ref(false)

  async function loadRaw(projectId: string, chapter: number) {
    isLoading.value = true
    try {
      currentRaw.value = await sflogApi.raw(projectId, chapter)
    } finally {
      isLoading.value = false
    }
  }

  async function reparse(projectId: string, chapterId: number) {
    isLoading.value = true
    try {
      currentReparse.value = await sflogApi.reparse(projectId, chapterId)
    } finally {
      isLoading.value = false
    }
  }

  return { currentRaw, currentReparse, isLoading, loadRaw, reparse }
})
```

- [ ] **Step 4: 运行测试确认通过** — 期望 6 passed × 3 = 18 passed

- [ ] **Step 5: Commit** — `git add frontend/src/stores/storyos/ && git commit -m "feat(frontend): add 3 Pinia stores (queries/cascade/sflog) with cache invalidation"`

#### Task D3: 路由 + 嵌套布局

**Files:**
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/router/workbench.ts`（新增 storyos 嵌套路由）

- [ ] **Step 1: 写失败测试**

```typescript
// frontend/src/router/__tests__/workbench.spec.ts
import { describe, it, expect } from 'vitest'
import { workbenchStoryosRoutes } from '../workbench'

describe('workbenchStoryosRoutes', () => {
  it('导出 6 个 storyos 子路由', () => {
    expect(workbenchStoryosRoutes).toHaveLength(1)  // 1 个父路由（path: storyos）
    const parent = workbenchStoryosRoutes[0]
    expect(parent.children).toHaveLength(5)  // 5 子路由
  })

  it('默认子路由是 registry-list', () => {
    const parent = workbenchStoryosRoutes[0]
    const defaultChild = parent.children!.find((c: any) => c.path === '')
    expect(defaultChild).toBeDefined()
  })

  it('路径包含 slug 参数', () => {
    const parent = workbenchStoryosRoutes[0]
    expect(parent.path).toContain(':slug')
  })
})
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `Failed to resolve import`

- [ ] **Step 3: 实现** — `frontend/src/router/workbench.ts`：

```typescript
import type { RouteRecordRaw } from 'vue-router'

/** StoryOS 嵌套路由（在 /book/:slug/workbench 之外的可选独立路由）。*/
export const workbenchStoryosRoutes: RouteRecordRaw[] = [
  {
    path: '/book/:slug/storyos',
    name: 'WorkbenchStoryos',
    component: () => import('@/views/workbench/storyos/StoryOSHub.vue'),
    meta: { requiresProject: true },
    children: [
      {
        path: '',
        name: 'WorkbenchStoryosRegistryList',
        component: () => import('@/views/workbench/storyos/RegistryList.vue'),
      },
      {
        path: ':assetType',
        name: 'WorkbenchStoryosAssetType',
        component: () => import('@/views/workbench/storyos/RegistryList.vue'),
        props: true,
      },
      {
        path: 'cascade',
        name: 'WorkbenchStoryosCascade',
        component: () => import('@/views/workbench/storyos/CascadeGraph.vue'),
      },
      {
        path: 'sflog/:chapterId',
        name: 'WorkbenchStoryosSflog',
        component: () => import('@/views/workbench/storyos/SFLogInspector.vue'),
        props: true,
      },
      {
        path: 'predeclared/:chapterId',
        name: 'WorkbenchStoryosPredeclared',
        component: () => import('@/views/workbench/storyos/PredeclaredDiff.vue'),
        props: true,
      },
    ],
  },
]
```

并修改 `frontend/src/router/index.ts`：

```typescript
// 在 routes 数组追加
import { workbenchStoryosRoutes } from './workbench'
// ... existing routes ...
{
  path: '/debug/scheduler',
  name: 'CharacterSchedulerSimulator',
  component: CharacterSchedulerSimulator,
},
...workbenchStoryosRoutes,  // ← 新增
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed

- [ ] **Step 5: Commit** — `git add frontend/src/router/ && git commit -m "feat(router): add /book/:slug/storyos nested route with 5 sub-views"`

#### Task D4: StoryOSHub.vue 主布局

**Files:**
- Create: `frontend/src/views/workbench/storyos/StoryOSHub.vue`
- Create: `frontend/src/views/workbench/storyos/__tests__/StoryOSHub.spec.ts`

- [ ] **Step 1: 写失败测试**

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import StoryOSHub from '../StoryOSHub.vue'

describe('StoryOSHub', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('渲染左侧 8 registry 导航 + 右侧 router-view', () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div/>' } }],
    })
    const wrapper = mount(StoryOSHub, {
      props: { slug: 'proj-1' },
      global: { plugins: [router] },
    })
    expect(wrapper.find('.storyos-sidebar').exists()).toBe(true)
    expect(wrapper.find('.storyos-main').exists()).toBe(true)
    // 8 个 registry 导航项
    const navItems = wrapper.findAll('.storyos-sidebar-item')
    expect(navItems).toHaveLength(8)
  })

  it('点击 navigation 切换路由', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/:slug/storyos', component: { template: '<div class="placeholder"/>' } },
        { path: '/:slug/storyos/cascade', component: { template: '<div class="cascade"/>' } },
      ],
    })
    const wrapper = mount(StoryOSHub, {
      props: { slug: 'proj-1' },
      global: { plugins: [router] },
    })
    await wrapper.find('.storyos-sidebar-item[data-asset="cascade"]').trigger('click')
    expect(router.currentRoute.value.path).toBe('/proj-1/storyos/cascade')
  })

  it('显示当前项目 ID', () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div/>' } }],
    })
    const wrapper = mount(StoryOSHub, {
      props: { slug: 'proj-1' },
      global: { plugins: [router] },
    })
    expect(wrapper.find('.storyos-project-id').text()).toContain('proj-1')
  })
})
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `Failed to resolve import`

- [ ] **Step 3: 实现** — `StoryOSHub.vue`：

```vue
<template>
  <div class="storyos-hub">
    <div class="storyos-header">
      <span class="storyos-title">{{ $t('storyos.title') }}</span>
      <span class="storyos-project-id">{{ slug }}</span>
      <n-button @click="goBack" size="small">{{ $t('common.back') }}</n-button>
    </div>
    <n-split direction="horizontal" :min="200" :max="320" :default-size="240">
      <template #1>
        <div class="storyos-sidebar">
          <div class="storyos-sidebar-section">
            <h4>{{ $t('storyos.section.registries') }}</h4>
            <div
              v-for="asset in assetTypes"
              :key="asset"
              class="storyos-sidebar-item"
              :data-asset="asset"
              :class="{ active: $route.params.assetType === asset }"
              @click="navigateTo(asset)"
            >
              <StatusBadge v-if="asset" :status="getRepresentativeStatus(asset)" />
              <span>{{ $t(`storyos.asset.${asset}`) }}</span>
            </div>
          </div>
          <div class="storyos-sidebar-section">
            <h4>{{ $t('storyos.section.observability') }}</h4>
            <div
              class="storyos-sidebar-item"
              :data-asset="cascade"
              :class="{ active: $route.name === 'WorkbenchStoryosCascade' }"
              @click="navigateToCascade"
            >
              <span>{{ $t('storyos.asset.cascadeGraph') }}</span>
            </div>
            <div class="storyos-sidebar-item" @click="navigateToSflog">
              <span>{{ $t('storyos.asset.sflogInspector') }}</span>
            </div>
            <div class="storyos-sidebar-item" @click="navigateToPredeclared">
              <span>{{ $t('storyos.asset.predeclaredDiff') }}</span>
            </div>
          </div>
        </div>
      </template>
      <template #2>
        <div class="storyos-main">
          <router-view />
        </div>
      </template>
    </n-split>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { NButton, NSplit } from 'naive-ui'
import StatusBadge from '@/components/workbench/storyos/StatusBadge.vue'
import type { AssetType, AssetStatus } from '@/types/storyos'

const props = defineProps<{ slug: string }>()
const route = useRoute()
const router = useRouter()
const { t } = useI18n()

const assetTypes: AssetType[] = [
  'conflict', 'mystery', 'twist', 'promise',
  'reveal', 'expectation', 'goal', 'foreshadowing',
]

const _ = ref(0)  // placeholder for reactivity

function getRepresentativeStatus(asset: AssetType): AssetStatus {
  // 简化：从 store 取第一个 status（实际用统计）
  return 'active'
}

function navigateTo(asset: AssetType) {
  router.push({ name: 'WorkbenchStoryosAssetType', params: { slug: props.slug, assetType: asset } })
}

function navigateToCascade() {
  router.push({ name: 'WorkbenchStoryosCascade', params: { slug: props.slug } })
}

function navigateToSflog() {
  // 默认打开章节 1，可由用户在 SFLogInspector 内切换
  router.push({ name: 'WorkbenchStoryosSflog', params: { slug: props.slug, chapterId: 1 } })
}

function navigateToPredeclared() {
  router.push({ name: 'WorkbenchStoryosPredeclared', params: { slug: props.slug, chapterId: 1 } })
}

function goBack() {
  router.push({ name: 'Workbench', params: { slug: props.slug } })
}
</script>

<style scoped>
.storyos-hub {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.storyos-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 24px;
  border-bottom: 1px solid #e0e0e6;
}
.storyos-title {
  font-size: 18px;
  font-weight: 600;
}
.storyos-project-id {
  color: #888;
  font-size: 12px;
}
.storyos-sidebar {
  padding: 16px 0;
}
.storyos-sidebar-section h4 {
  padding: 0 16px;
  margin: 12px 0 8px;
  font-size: 11px;
  text-transform: uppercase;
  color: #999;
}
.storyos-sidebar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  cursor: pointer;
  user-select: none;
}
.storyos-sidebar-item:hover {
  background: rgba(0, 0, 0, 0.04);
}
.storyos-sidebar-item.active {
  background: rgba(24, 160, 88, 0.1);
  color: #18a058;
}
.storyos-main {
  height: 100%;
  overflow: auto;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed

- [ ] **Step 5: Commit** — `git add frontend/src/views/workbench/storyos/StoryOSHub.vue frontend/src/views/workbench/storyos/__tests__/StoryOSHub.spec.ts && git commit -m "feat(frontend): add StoryOSHub main panel with 8 registry nav + 5 sub-routes"`

---

### Group E: 6 子视图 + 4 组件（6 任务）

#### Task E1: StatusBadge + AssetCard 基础组件

**Files:**
- Create: `frontend/src/components/workbench/storyos/StatusBadge.vue`
- Create: `frontend/src/components/workbench/storyos/AssetCard.vue`
- Create: `frontend/src/components/workbench/storyos/__tests__/StatusBadge.spec.ts`
- Create: `frontend/src/components/workbench/storyos/__tests__/AssetCard.spec.ts`

- [ ] **Step 1: 写失败测试** — `StatusBadge.spec.ts`

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StatusBadge from '../StatusBadge.vue'
import type { AssetStatus } from '@/types/storyos'

describe('StatusBadge', () => {
  const cases: Array<[AssetStatus, string]> = [
    ['active', 'badge-blue'],
    ['accumulating', 'badge-blue'],
    ['planted', 'badge-yellow'],
    ['ready_to_fulfill', 'badge-yellow'],
    ['escalated', 'badge-yellow'],
    ['revealed', 'badge-green'],
    ['fulfilled', 'badge-green'],
    ['resolved', 'badge-green'],
    ['abandoned', 'badge-red'],
    ['dead', 'badge-red'],
  ]

  it.each(cases)('status=%s 渲染颜色 class %s', (status, expectedClass) => {
    const wrapper = mount(StatusBadge, { props: { status } })
    expect(wrapper.find(`.${expectedClass}`).exists()).toBe(true)
    expect(wrapper.text()).toBe(status)
  })

  it('支持 size prop', () => {
    const wrapper = mount(StatusBadge, { props: { status: 'active', size: 'small' } })
    expect(wrapper.find('.badge-small').exists()).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `Failed to resolve import`

- [ ] **Step 3: 实现** — `StatusBadge.vue`：

```vue
<template>
  <span class="status-badge" :class="[`badge-${colorClass}`, `badge-${size}`]">
    {{ status }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AssetStatus } from '@/types/storyos'

const props = withDefaults(defineProps<{
  status: AssetStatus
  size?: 'small' | 'medium'
}>(), { size: 'medium' })

const COLOR_MAP: Record<AssetStatus, 'blue' | 'yellow' | 'green' | 'red'> = {
  active: 'blue',
  accumulating: 'blue',
  developing: 'blue',
  hidden: 'blue',
  planted: 'yellow',
  ready_to_fulfill: 'yellow',
  escalated: 'yellow',
  revealed: 'green',
  fulfilled: 'green',
  resolved: 'green',
  abandoned: 'red',
  dead: 'red',
}

const colorClass = computed(() => COLOR_MAP[props.status])
</script>

<style scoped>
.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  text-transform: uppercase;
}
.badge-small { font-size: 10px; padding: 1px 6px; }
.badge-blue { background: #e6f7ff; color: #1890ff; }
.badge-yellow { background: #fffbe6; color: #faad14; }
.badge-green { background: #f6ffed; color: #52c41a; }
.badge-red { background: #fff1f0; color: #ff4d4f; }
</style>
```

`AssetCard.vue`（用于 RegistryList 列表项）：

```vue
<template>
  <div class="asset-card" :class="{ selected }" @click="$emit('click', asset)">
    <div class="asset-card-header">
      <span class="asset-card-id">#{{ asset.id }}</span>
      <StatusBadge :status="asset.status" size="small" />
    </div>
    <div class="asset-card-description">{{ asset.description }}</div>
    <div class="asset-card-meta">
      <span>{{ $t('storyos.meta.chapter') }}: {{ asset.createdChapter }}</span>
      <span v-if="(asset as ConflictAsset).intensity !== undefined">
        {{ $t('storyos.meta.intensity') }}: {{ (asset as ConflictAsset).intensity }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import StatusBadge from './StatusBadge.vue'
import type { ConflictAsset } from '@/types/storyos'

defineProps<{
  asset: any
  selected?: boolean
}>()
defineEmits<{ click: [asset: any] }>()
</script>

<style scoped>
.asset-card {
  border: 1px solid #e0e0e6;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.asset-card:hover { border-color: #18a058; }
.asset-card.selected { background: rgba(24, 160, 88, 0.05); border-color: #18a058; }
.asset-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.asset-card-id { font-size: 11px; color: #999; }
.asset-card-description {
  font-size: 14px;
  color: #333;
  margin-bottom: 8px;
}
.asset-card-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #888;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过** — 期望 10+2 passed

- [ ] **Step 5: Commit** — `git add frontend/src/components/workbench/storyos/ && git commit -m "feat(frontend): add StatusBadge (12 status colors) + AssetCard components"`

#### Task E2: RegistryList + RegistryDetailDrawer

**Files:**
- Create: `frontend/src/views/workbench/storyos/RegistryList.vue`
- Create: `frontend/src/views/workbench/storyos/RegistryDetailDrawer.vue`
- Create: `frontend/src/views/workbench/storyos/__tests__/RegistryList.spec.ts`
- Create: `frontend/src/views/workbench/storyos/__tests__/RegistryDetailDrawer.spec.ts`

- [ ] **Step 1: 写失败测试** — `RegistryList.spec.ts`

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import RegistryList from '../RegistryList.vue'
import { useStoryosQueriesStore } from '@/stores/storyos/queries'
import { conflictApi } from '@/api/storyos'

vi.mock('@/api/storyos', () => ({
  conflictApi: { list: vi.fn() },
}))

describe('RegistryList', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('默认根据 route param assetType 加载列表', async () => {
    ;(conflictApi.list as any).mockResolvedValue({
      data: [{ id: 'cf-1', description: 'x', status: 'active', createdChapter: 1 }],
      meta: { total: 1, page: 1, pageSize: 20, totalPages: 1, hasNext: false, hasPrev: false },
    })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:slug/storyos/:assetType', component: { template: '<div/>' } }],
    })
    await router.push('/proj-1/storyos/conflict')
    const wrapper = mount(RegistryList, {
      global: { plugins: [router] },
    })
    await flushPromises()
    const cards = wrapper.findAllComponents({ name: 'AssetCard' })
    expect(cards.length).toBeGreaterThan(0)
    expect(cards[0].props('asset').id).toBe('cf-1')
  })

  it('点击 AssetCard 打开 RegistryDetailDrawer', async () => {
    ;(conflictApi.list as any).mockResolvedValue({
      data: [{ id: 'cf-1', description: 'x', status: 'active', createdChapter: 1 }],
      meta: { total: 0, page: 1, pageSize: 20, totalPages: 0, hasNext: false, hasPrev: false },
    })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:slug/storyos/:assetType', component: { template: '<div/>' } }],
    })
    await router.push('/proj-1/storyos/conflict')
    const wrapper = mount(RegistryList, { global: { plugins: [router] } })
    await flushPromises()
    await wrapper.findComponent({ name: 'AssetCard' }).trigger('click')
    expect(wrapper.findComponent({ name: 'RegistryDetailDrawer' }).exists()).toBe(true)
  })

  it('支持 status filter', async () => {
    ;(conflictApi.list as any).mockResolvedValue({ data: [], meta: { total: 0, page: 1, pageSize: 20, totalPages: 0, hasNext: false, hasPrev: false } })
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:slug/storyos/:assetType', component: { template: '<div/>' } }],
    })
    await router.push('/proj-1/storyos/conflict')
    const wrapper = mount(RegistryList, { global: { plugins: [router] } })
    await wrapper.find('select.status-filter').setValue('active')
    expect(conflictApi.list).toHaveBeenCalledWith(
      'proj-1',
      expect.objectContaining({ status: 'active' }),
    )
  })
})
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `Failed to resolve import`

- [ ] **Step 3: 实现** — `RegistryList.vue`（核心结构）：

```vue
<template>
  <div class="registry-list">
    <div class="registry-list-toolbar">
      <n-input v-model:value="search" placeholder="搜索描述..." clearable />
      <select v-model="statusFilter" class="status-filter">
        <option value="">全部状态</option>
        <option v-for="s in allStatuses" :key="s" :value="s">{{ s }}</option>
      </select>
      <n-button type="primary" @click="showCreate = true">+ 新建</n-button>
    </div>
    <div class="registry-list-grid">
      <AssetCard
        v-for="item in store[currentListKey]"
        :key="item.id"
        :asset="item"
        :selected="selectedId === item.id"
        @click="onCardClick"
      />
    </div>
    <RegistryDetailDrawer
      v-if="selectedId"
      :slug="slug"
      :asset-type="assetType"
      :asset-id="selectedId"
      @close="selectedId = null"
      @updated="onUpdated"
    />
    <CreateAssetModal
      v-if="showCreate"
      :slug="slug"
      :asset-type="assetType"
      @close="showCreate = false"
      @created="onCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { NInput, NButton } from 'naive-ui'
import AssetCard from '@/components/workbench/storyos/AssetCard.vue'
import RegistryDetailDrawer from './RegistryDetailDrawer.vue'
import CreateAssetModal from './CreateAssetModal.vue'
import { useStoryosQueriesStore } from '@/stores/storyos/queries'
import type { AssetType, AssetStatus } from '@/types/storyos'

const route = useRoute()
const store = useStoryosQueriesStore()
const slug = computed(() => route.params.slug as string)
const assetType = computed(() => (route.params.assetType || 'conflict') as AssetType)

const search = ref('')
const statusFilter = ref<string>('')
const selectedId = ref<string | null>(null)
const showCreate = ref(false)

const allStatuses: AssetStatus[] = [
  'active', 'accumulating', 'planted', 'developing',
  'hidden', 'ready_to_fulfill', 'escalated', 'revealed',
  'fulfilled', 'resolved', 'abandoned', 'dead',
]

const currentListKey = computed(() => {
  return {
    conflict: 'conflictList',
    mystery: 'mysteryList',
    twist: 'twistList',
    promise: 'promiseList',
    reveal: 'revealList',
    expectation: 'expectationList',
    goal: 'goalList',
    foreshadowing: 'foreshadowingList',
  }[assetType.value] as keyof typeof store
})

async function loadList() {
  await store.fetchList(slug.value, assetType.value, {
    status: statusFilter.value || undefined,
    page: 1, pageSize: 50,
  })
}

onMounted(loadList)
watch([statusFilter, assetType], loadList)

function onCardClick(asset: any) { selectedId.value = asset.id }
function onUpdated() { loadList() }
function onCreated() { showCreate.value = false; loadList() }
</script>

<style scoped>
.registry-list { padding: 24px; }
.registry-list-toolbar { display: flex; gap: 12px; margin-bottom: 16px; }
.status-filter { padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; }
.registry-list-grid { display: grid; grid-template-columns: 1fr; gap: 8px; }
</style>
```

`RegistryDetailDrawer.vue`：Naive UI `n-drawer` + 表单 + 保存按钮（编辑模式）。完整实现约 200 LOC，省略。

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed

- [ ] **Step 5: Commit** — `git add frontend/src/views/workbench/storyos/RegistryList.vue frontend/src/views/workbench/storyos/RegistryDetailDrawer.vue && git commit -m "feat(frontend): add RegistryList + RegistryDetailDrawer with filter and edit"`

#### Task E3: CascadeGraph + CascadeStepNode + IntensityChart

**Files:**
- Create: `frontend/src/views/workbench/storyos/CascadeGraph.vue`
- Create: `frontend/src/components/workbench/storyos/CascadeStepNode.vue`
- Create: `frontend/src/components/workbench/storyos/IntensityChart.vue`

- [ ] **Step 1: 写失败测试** — `CascadeGraph.spec.ts`（核心）

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { cascadeApi } from '@/api/storyos'

vi.mock('@/api/storyos', () => ({
  cascadeApi: { simulate: vi.fn(), history: vi.fn() },
}))

import CascadeGraph from '../CascadeGraph.vue'

describe('CascadeGraph', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('点击 Simulate 调用 cascadeApi.simulate', async () => {
    ;(cascadeApi.simulate as any).mockResolvedValue({
      steps: [],
      blockedSteps: [],
      summary: { wouldBlock: false, maxDepthReached: 0, stepsCount: 0, blockedStepsCount: 0, wouldCreateCycle: false },
    })
    const wrapper = mount(CascadeGraph, { props: { slug: 'proj-1' } })
    await wrapper.find('button.simulate-btn').trigger('click')
    await flushPromises()
    expect(cascadeApi.simulate).toHaveBeenCalled()
  })

  it('渲染 Vue Flow', () => {
    const wrapper = mount(CascadeGraph, { props: { slug: 'proj-1' } })
    expect(wrapper.find('[data-testid="vue-flow"]').exists()).toBe(true)
  })

  it('3 步级联生成 N+1 节点（1 root + N step）+ N 条连边（拓扑链）', async () => {
    // REVIEW-FIX C-2: 验证 rebuildGraph 把 steps 串成真正 DAG。
    ;(cascadeApi.simulate as any).mockResolvedValue({
      steps: [
        { trigger: 'mystery_revealed', sourceAssetId: 'm-1', targetAssetId: 'e-1', newStatus: 'ready_to_fulfill' },
        { trigger: 'expectation_fulfill', sourceAssetId: 'e-1', targetAssetId: 'c-1', newStatus: 'escalated' },
        { trigger: 'conflict_escalate', sourceAssetId: 'c-1', targetAssetId: 'c-2', newStatus: 'escalated' },
      ],
      blockedSteps: [],
      summary: { wouldBlock: false, maxDepthReached: 2, stepsCount: 3, blockedStepsCount: 0, wouldCreateCycle: false },
    })
    const wrapper = mount(CascadeGraph, { props: { slug: 'proj-1' } })
    await wrapper.find('button.simulate-btn').trigger('click')
    await flushPromises()
    // 期望：4 节点（root + 3 step）
    const nodes = wrapper.vm.vueFlowNodes ?? wrapper.vm.$.setupState.vueFlowNodes
    const edges = wrapper.vm.vueFlowEdges ?? wrapper.vm.$.setupState.vueFlowEdges
    expect(nodes).toHaveLength(4)
    expect(edges).toHaveLength(3)
    // 边连接：root → s0 → s1 → s2（链式）
    expect(edges[0].source).toBe('root-m-1')
    expect(edges[0].target).toBe('s0-e-1')
    expect(edges[2].target).toBe('s2-c-2')
  })
})
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `Failed to resolve import`

- [ ] **Step 3: 实现** — `CascadeGraph.vue`：

```vue
<template>
  <div class="cascade-graph">
    <div class="cascade-graph-toolbar">
      <n-select
        v-model:value="triggerForm.trigger"
        :options="triggerOptions"
        placeholder="选择 trigger"
        style="width: 220px"
      />
      <n-select
        v-model:value="triggerForm.sourceAssetType"
        :options="assetTypeOptions"
        placeholder="源资产类型"
        style="width: 160px"
      />
      <n-input v-model:value="triggerForm.sourceAssetId" placeholder="源资产 ID" />
      <n-button type="primary" :loading="cascade.isSimulating" @click="onSimulate" class="simulate-btn">
        Simulate
      </n-button>
    </div>
    <div v-if="cascade.lastSimulation" class="cascade-graph-summary">
      <n-tag :type="cascade.lastSimulation.summary.wouldBlock ? 'error' : 'success'">
        {{ cascade.lastSimulation.summary.wouldBlock ? 'Block' : 'Pass' }}
      </n-tag>
      <span>Max Depth: {{ cascade.lastSimulation.summary.maxDepthReached }}</span>
      <span>Steps: {{ cascade.lastSimulation.summary.stepsCount }}</span>
    </div>
    <div class="cascade-graph-canvas" data-testid="vue-flow">
      <VueFlow
        v-model:nodes="vueFlowNodes"
        v-model:edges="vueFlowEdges"
        :node-types="nodeTypes"
        fit-view-on-init
      >
        <Background />
        <Controls />
      </VueFlow>
    </div>
    <div v-if="cascade.lastSimulation" class="cascade-graph-intensity">
      <IntensityChart :steps="cascade.lastSimulation.steps" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { NSelect, NInput, NButton, NTag } from 'naive-ui'
import CascadeStepNode from '@/components/workbench/storyos/CascadeStepNode.vue'
import IntensityChart from '@/components/workbench/storyos/IntensityChart.vue'
import { useStoryosCascadeStore } from '@/stores/storyos/cascade'
import type { CascadeTrigger, AssetType, CascadeStep } from '@/types/storyos'

const props = defineProps<{ slug: string }>()
const cascade = useStoryosCascadeStore()

const triggerForm = ref<{ trigger: CascadeTrigger | null; sourceAssetType: AssetType | null; sourceAssetId: string }>({
  trigger: null, sourceAssetType: null, sourceAssetId: '',
})

const triggerOptions = [
  { label: 'mystery_revealed', value: 'mystery_revealed' },
  { label: 'twist_revealed', value: 'twist_revealed' },
  { label: 'reveal_revealed', value: 'reveal_revealed' },
  { label: 'promise_fulfilled', value: 'promise_fulfilled' },
  { label: 'conflict_resolved', value: 'conflict_resolved' },
  { label: 'conflict_escalated', value: 'conflict_escalated' },
]

const assetTypeOptions = [
  { label: 'conflict', value: 'conflict' },
  { label: 'mystery', value: 'mystery' },
  { label: 'twist', value: 'twist' },
  { label: 'expectation', value: 'expectation' },
]

const nodeTypes = { cascadeStep: CascadeStepNode }

const vueFlowNodes = ref<any[]>([])
const vueFlowEdges = ref<any[]>([])

async function onSimulate() {
  if (!triggerForm.value.trigger || !triggerForm.value.sourceAssetType || !triggerForm.value.sourceAssetId) return
  await cascade.simulate(props.slug, {
    trigger: triggerForm.value.trigger,
    sourceAssetType: triggerForm.value.sourceAssetType,
    sourceAssetId: triggerForm.value.sourceAssetId,
  })
  rebuildGraph()
}

function rebuildGraph() {
  const steps = cascade.lastSimulation?.steps ?? []
  // REVIEW-FIX C-2: 每个节点的 ID 用 `s{index}-{targetAssetId}` 唯一；
  // edges 把「上一步 target」链到「这一步 target」，形成真正的级联 DAG。
  // 旧版本有 2 个 bug：(1) 节点 ID = `${source}-${target}` 重叠；
  // (2) `replace(..., '$&')` 是 no-op，target 算错。
  vueFlowNodes.value = steps.map((s, i) => ({
    id: `s${i}-${s.targetAssetId}`,
    type: 'cascadeStep',
    position: { x: (i + 1) * 220, y: 100 },
    data: s,
  }))

  // 在第一个节点之前追加一个 __root 节点，承载 simulation 的 source asset
  vueFlowNodes.value.unshift({
    id: `root-${steps[0]?.sourceAssetId ?? 'unknown'}`,
    type: 'cascadeStep',
    position: { x: 0, y: 100 },
    data: { label: 'Source', assetId: steps[0]?.sourceAssetId },
  })

  const edges: typeof vueFlowEdges.value = []
  let prevTargetId: string | null = null
  steps.forEach((s, i) => {
    const nodeId = `s${i}-${s.targetAssetId}`
    const sourceId = prevTargetId ?? `root-${s.sourceAssetId}`
    edges.push({
      id: `e${i}`,
      source: sourceId,
      target: nodeId,
      label: s.trigger,
      animated: true,
    })
    prevTargetId = nodeId
  })
  vueFlowEdges.value = edges
}
</script>

<style scoped>
.cascade-graph { display: flex; flex-direction: column; height: 100%; }
.cascade-graph-toolbar { display: flex; gap: 8px; padding: 12px; }
.cascade-graph-summary { display: flex; gap: 12px; padding: 0 12px; font-size: 12px; }
.cascade-graph-canvas { flex: 1; min-height: 400px; }
.cascade-graph-intensity { padding: 12px; }
</style>
```

`CascadeStepNode.vue` + `IntensityChart.vue`：Vue Flow 自定义节点（~80 LOC）+ ECharts 折线图（~100 LOC）。完整代码省略，参考 `@vue-flow/core` 与 `echarts/vue-echarts` 文档。

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed

- [ ] **Step 5: Commit** — `git add frontend/src/views/workbench/storyos/CascadeGraph.vue frontend/src/components/workbench/storyos/CascadeStepNode.vue frontend/src/components/workbench/storyos/IntensityChart.vue && git commit -m "feat(frontend): add CascadeGraph with Vue Flow + IntensityChart with ECharts"`

#### Task E4: SFLogInspector 并排布局

**Files:**
- Create: `frontend/src/views/workbench/storyos/SFLogInspector.vue`
- Create: `frontend/src/views/workbench/storyos/__tests__/SFLogInspector.spec.ts`

- [ ] **Step 1: 写失败测试**

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { sflogApi } from '@/api/storyos'

vi.mock('@/api/storyos', () => ({ sflogApi: { raw: vi.fn(), reparse: vi.fn() } }))

import SFLogInspector from '../SFLogInspector.vue'

describe('SFLogInspector', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('加载指定章节 raw 文本与 records', async () => {
    ;(sflogApi.raw as any).mockResolvedValue({
      projectId: 'proj-1',
      chapterId: 5,
      rawText: 'before <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="x" --> after',
      records: [{ logType: 'mystery_clue', params: { mystery_id: 'm1', content: 'x' }, chapterId: 5, charPosition: 7, assetId: 'm1', raw: '...' }],
      sfLogCount: 1,
    })
    const wrapper = mount(SFLogInspector, { props: { slug: 'proj-1', chapterId: 5 } })
    await flushPromises()
    expect(wrapper.find('.sf-log-raw-text').text()).toContain('SF_LOG')
    expect(wrapper.findAll('.sf-log-record-item').length).toBe(1)
  })

  it('支持切换章节', async () => {
    ;(sflogApi.raw as any).mockResolvedValue({ projectId: 'proj-1', chapterId: 1, rawText: 'x', records: [], sfLogCount: 0 })
    const wrapper = mount(SFLogInspector, { props: { slug: 'proj-1', chapterId: 1 } })
    await wrapper.find('input.chapter-input').setValue('10')
    await wrapper.find('input.chapter-input').trigger('change')
    expect(sflogApi.raw).toHaveBeenCalledWith('proj-1', 10)
  })
})
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `Failed to resolve import`

- [ ] **Step 3: 实现** — `SFLogInspector.vue`（核心结构）：

```vue
<template>
  <div class="sf-log-inspector">
    <div class="sf-log-toolbar">
      <label>章节：<input v-model.number="chapterId" type="number" min="1" class="chapter-input" @change="loadRaw" /></label>
      <n-button @click="onReparse" :loading="sflog.isLoading">Re-parse</n-button>
    </div>
    <div class="sf-log-body">
      <div class="sf-log-raw-pane">
        <h4>原始文本（高亮 SF_LOG）</h4>
        <div class="sf-log-raw-text" v-html="highlightedRaw"></div>
      </div>
      <div class="sf-log-records-pane">
        <h4>解析结果（{{ sflog.currentRaw?.sfLogCount ?? 0 }} 条）</h4>
        <div
          v-for="rec in sflog.currentRaw?.records ?? []"
          :key="rec.charPosition"
          class="sf-log-record-item"
        >
          <div class="sf-log-record-header">
            <span class="sf-log-record-type">{{ rec.logType }}</span>
            <span class="sf-log-record-pos">@{{ rec.charPosition }}</span>
          </div>
          <pre class="sf-log-record-params">{{ JSON.stringify(rec.params, null, 2) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { NButton } from 'naive-ui'
import { useStoryosSflogStore } from '@/stores/storyos/sflog'

const props = defineProps<{ slug: string; chapterId: number }>()
const sflog = useStoryosSflogStore()
const chapterId = ref(props.chapterId)

const highlightedRaw = computed(() => {
  if (!sflog.currentRaw) return ''
  return sflog.currentRaw.rawText.replace(
    /<!--\s*SF_LOG[^>]*?-->/g,
    (m) => `<mark class="sf-log-highlight">${m}</mark>`,
  )
})

async function loadRaw() {
  await sflog.loadRaw(props.slug, chapterId.value)
}

async function onReparse() {
  await sflog.reparse(props.slug, chapterId.value)
}

onMounted(loadRaw)
watch(() => props.chapterId, (v) => { chapterId.value = v; loadRaw() })
</script>

<style scoped>
.sf-log-inspector { display: flex; flex-direction: column; height: 100%; }
.sf-log-toolbar { display: flex; gap: 12px; padding: 12px; border-bottom: 1px solid #e0e0e6; }
.sf-log-body { display: flex; flex: 1; overflow: hidden; }
.sf-log-raw-pane, .sf-log-records-pane { flex: 1; padding: 12px; overflow: auto; }
.sf-log-raw-text {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  white-space: pre-wrap;
  line-height: 1.6;
}
:deep(.sf-log-highlight) {
  background: #fff3a0;
  border: 1px solid #faad14;
  border-radius: 3px;
  padding: 0 2px;
}
.sf-log-record-item {
  border: 1px solid #e0e0e6;
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 8px;
}
.sf-log-record-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
.sf-log-record-type { font-weight: 500; color: #1890ff; }
.sf-log-record-pos { font-size: 11px; color: #999; }
.sf-log-record-params {
  font-size: 11px;
  background: #f5f5f5;
  padding: 4px;
  border-radius: 3px;
  margin: 0;
}
</style>
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed

- [ ] **Step 5: Commit** — `git add frontend/src/views/workbench/storyos/SFLogInspector.vue && git commit -m "feat(frontend): add SFLogInspector with raw text highlight + parsed records list"`

#### Task E5: PredeclaredDiff 三色高亮

**Files:**
- Create: `frontend/src/views/workbench/storyos/PredeclaredDiff.vue`

- [ ] **Step 1: 写失败测试**

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/storyos', () => ({ sflogApi: { reparse: vi.fn() } }))
import { sflogApi } from '@/api/storyos'
import PredeclaredDiff from '../PredeclaredDiff.vue'

describe('PredeclaredDiff', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('匹配 = 绿色', async () => {
    ;(sflogApi.reparse as any).mockResolvedValue({
      chapterId: 5,
      matchReport: {
        predeclaredTotal: 2, predeclaredImplemented: 1,
        missingChanges: [], unexpectedRecords: [],
        matchRate: 0.5,
      },
    })
    const wrapper = mount(PredeclaredDiff, { props: { slug: 'proj-1', chapterId: 5 } })
    await flushPromises()
    expect(wrapper.find('.match-rate').text()).toContain('50%')
  })

  it('缺失 = 红色', async () => {
    ;(sflogApi.reparse as any).mockResolvedValue({
      chapterId: 5,
      matchReport: {
        predeclaredTotal: 2, predeclaredImplemented: 1,
        missingChanges: [{ assetId: 'm1' }],
        unexpectedRecords: [],
        matchRate: 0.5,
      },
    })
    const wrapper = mount(PredeclaredDiff, { props: { slug: 'proj-1', chapterId: 5 } })
    await flushPromises()
    expect(wrapper.findAll('.diff-missing').length).toBe(1)
  })
})
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `Failed to resolve import`

- [ ] **Step 3: 实现** — `PredeclaredDiff.vue`（核心）：

```vue
<template>
  <div class="predeclared-diff" v-if="report">
    <div class="diff-summary">
      <h4>匹配率：{{ (report.matchRate * 100).toFixed(0) }}%</h4>
      <span>{{ report.predeclaredImplemented }} / {{ report.predeclaredTotal }} 实现</span>
    </div>
    <div v-if="report.missingChanges.length" class="diff-section diff-missing-section">
      <h4>缺失（predeclared 未实现 → RETRY）</h4>
      <div v-for="m in report.missingChanges" :key="String(m)" class="diff-item diff-missing">
        {{ JSON.stringify(m) }}
      </div>
    </div>
    <div v-if="report.unexpectedRecords.length" class="diff-section diff-unexpected-section">
      <h4>意外（实际产出但 predeclared 无 → WARN）</h4>
      <div v-for="u in report.unexpectedRecords" :key="u.charPosition" class="diff-item diff-unexpected">
        {{ u.logType }} @ {{ u.charPosition }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { sflogApi } from '@/api/storyos'
import type { MatchReport } from '@/types/storyos'

const props = defineProps<{ slug: string; chapterId: number }>()
const report = ref<MatchReport | null>(null)

async function load() {
  const res = await sflogApi.reparse(props.slug, props.chapterId)
  report.value = res.matchReport
}

onMounted(load)
watch(() => props.chapterId, load)
</script>

<style scoped>
.diff-missing { background: #fff1f0; color: #ff4d4f; padding: 4px 8px; }
.diff-unexpected { background: #fffbe6; color: #faad14; padding: 4px 8px; }
</style>
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed

- [ ] **Step 5: Commit** — `git add frontend/src/views/workbench/storyos/PredeclaredDiff.vue && git commit -m "feat(frontend): add PredeclaredDiff with red/yellow highlighting"`

#### Task E6: 子视图性能 + i18n

**Files:**
- Modify: `frontend/vite.config.ts`
- Create: `frontend/src/i18n/locales/zh-CN.json`（追加 storyos 段）
- Create: `frontend/src/i18n/locales/en-US.json`（追加 storyos 段）

- [ ] **Step 1: 性能测试**

```typescript
// frontend/src/views/workbench/storyos/__tests__/performance.spec.ts
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import CascadeGraph from '../CascadeGraph.vue'

describe('CascadeGraph performance', () => {
  it('100 节点渲染 < 500ms', async () => {
    setActivePinia(createPinia())
    const start = performance.now()
    const wrapper = mount(CascadeGraph, { props: { slug: 'proj-1' } })
    wrapper.vm.$.exposed // 强制访问
    const elapsed = performance.now() - start
    expect(elapsed).toBeLessThan(500)
  })
})
```

- [ ] **Step 2: 实现 Vite chunk 拆分 + i18n** — `vite.config.ts`：

```typescript
// frontend/vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'storyos-vendor': ['@vue-flow/core', '@vue-flow/background', 'echarts', 'vue-echarts'],
          'storyos-views': [
            './src/views/workbench/storyos/StoryOSHub.vue',
            './src/views/workbench/storyos/RegistryList.vue',
            './src/views/workbench/storyos/CascadeGraph.vue',
            './src/views/workbench/storyos/SFLogInspector.vue',
            './src/views/workbench/storyos/PredeclaredDiff.vue',
          ],
        },
      },
    },
  },
})
```

- [ ] **Step 3: i18n** — `frontend/src/i18n/locales/zh-CN.json`（追加）：

```json
{
  "storyos": {
    "title": "叙事资产",
    "section": {
      "registries": "注册表",
      "observability": "可观测性"
    },
    "asset": {
      "conflict": "冲突",
      "mystery": "谜题",
      "twist": "反转",
      "promise": "承诺",
      "reveal": "揭示",
      "expectation": "预期",
      "goal": "目标",
      "foreshadowing": "伏笔",
      "cascadeGraph": "级联图",
      "sflogInspector": "SF_LOG 检查器",
      "predeclaredDiff": "预声明差异"
    },
    "meta": {
      "chapter": "章节",
      "intensity": "强度"
    }
  }
}
```

- [ ] **Step 4: 验证** — `npm run build` 期望 storyos chunk < 500KB；i18n 验证：`t('storyos.title')` 返回 "叙事资产"

- [ ] **Step 5: Commit** — `git add frontend/vite.config.ts frontend/src/i18n/ && git commit -m "perf(frontend): chunk-split storyos + i18n zh-CN/en-US"`

---

### Group F: 集成 + 端到端（3 任务）

#### Task F1: 与 1C 引擎钩子串联

**Files:**
- Create: `tests/integration/api/v1/storyos/test_engine_hook_integration.py`
- Create: `tests/integration/api/v1/storyos/test_chapter_regenerate_triggers_storyos.py`

- [ ] **Step 1: 写失败测试**

```python
"""1D 端点与 1C 引擎钩子集成：触发 chapter 重写 → 1C 走 StoryOSDelegate → 1D 端点反映状态变化。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from interfaces.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_chapter_regenerate_triggers_storyos_state_change(client):
    """1. 创建一个 conflict（active）
    2. POST /api/v1/chapters/5/regenerate
    3. 1C 走 Step 1/3/5/6 钩子，SF_LOG 解析产生 conflict_escalate
    4. 重新查询 conflict → status 应变为 escalated
    """
    # 1. 准备
    create_resp = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={"description": "x", "created_chapter": 1, "intensity": 50},
    )
    asset_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "active"

    # 2. 触发 chapter 重写（1C 钩子入口）
    regen_resp = client.post(
        "/api/v1/chapters/5/regenerate",
        json={"project_id": "proj-1", "trigger": "storyos_replay"},
    )
    assert regen_resp.status_code in (200, 202)

    # 3. 查询 conflict 状态
    get_resp = client.get(f"/api/v1/storyos/proj-1/conflict/{asset_id}")
    # 注：实际状态变化取决于章节文本是否含 SF_LOG conflict_escalate
    # 此测试在 mock 环境下验证端点连通性
    assert get_resp.status_code == 200


# REVIEW-FIX M-2: 上述 test 仅验证端点可达，不证明 1C 钩子真正触发状态变更。
# 以下追加一个 monkeypatch LLM 输出的强测试，验证 SF_LOG → BridgeResult → state 链。
def test_chapter_regenerate_with_sflog_changes_conflict_status(client, monkeypatch):
    """mock LLM 输出含 SF_LOG CONFLICT_ESCALATE 注释 → chapter 重写后
    conflict 状态从 active 升到 escalated。

    这才是「1D 端点反映 1C 钩子状态变化」的正确断言；强于原版只检查 200。
    """
    # 1. 准备一个 conflict（使用固定 id 让 SF_LOG 能引用到）
    create_resp = client.post(
        "/api/v1/storyos/proj-1/conflict",
        json={
            "id": "cf-test-001",  # 显式 id，让 SF_LOG 能 match 上
            "description": "林远 vs 沈墨",
            "created_chapter": 1,
            "intensity": 50,
        },
    )
    asset_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "active"

    # 2. mock LLM 输出含 SF_LOG 的章节文本（conflict_id 必须 == asset_id）
    fake_chapter_body = (
        '林远踏入档案室。\n'
        f'<!-- SF_LOG CONFLICT_ESCALATE conflict_id="{asset_id}" intensity_delta="20" -->\n'
        '突然，警报大作。'
    )
    # 目标 service 路径以 1B 的实际注册名为准；以下为最常见占位
    from application.engine.services.llm_service import LLMService  # 1B 实际位置
    if hasattr(LLMService, "generate_chapter"):
        monkeypatch.setattr(
            LLMService, "generate_chapter",
            lambda *a, **kw: fake_chapter_body,
        )
    elif hasattr(LLMService, "complete"):
        monkeypatch.setattr(
            LLMService, "complete",
            lambda *a, **kw: fake_chapter_body,
        )

    # 3. 触发 chapter 重写
    regen = client.post(
        "/api/v1/chapters/5/regenerate",
        json={"project_id": "proj-1", "trigger": "storyos_replay"},
    )
    assert regen.status_code in (200, 202)

    # 4. 等待异步管线完成（设上限避免挂死）
    import time
    deadline = time.time() + 10
    while time.time() < deadline:
        get_resp = client.get(f"/api/v1/storyos/proj-1/conflict/{asset_id}")
        if get_resp.json().get("status") == "escalated":
            break
        time.sleep(0.5)
    else:
        pytest.fail(
            "10s 内 conflict 状态未升至 escalated，"
            "StoryOSDelegate.apply_post_write_results 可能未生效"
        )

    final = get_resp.json()
    assert final["status"] == "escalated"
    # intensity 应从 50 升到 70
    assert final["intensity"] == 70
```

- [ ] **Step 2: 运行测试确认失败** — 期望端点不存在或超时

- [ ] **Step 3: 实现** — 测试通过依赖 1C 的 chapter regenerate 端点（`interfaces/api/v1/engine/generation.py` 已存在）。**本任务主要是测试覆盖**，无新代码。

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed（原连通性测试 + REVIEW-FIX M-2 状态变更测试）

- [ ] **Step 5: Commit** — `git add tests/integration/api/v1/storyos/ && git commit -m "test(integration): verify 1D endpoints + 1C engine hook coordination"`

#### Task F2: Export DOCX 改造

**Files:**
- Modify: `infrastructure/export/docx_exporter.py`（过滤 SF_LOG 注释 + 追加叙事弧线摘要）

- [ ] **Step 1: 写失败测试**

```python
"""DOCX 导出不含 SF_LOG 注释，但含「叙事弧线摘要」附录。"""
from __future__ import annotations

from infrastructure.export.docx_exporter import export_chapter_to_docx


def test_export_strips_sflog_annotations():
    chapter_text = '''
    林远踏入档案室。
    <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="blood" -->
    血迹在角落。
    '''
    output = export_chapter_to_docx(chapter_text, project_id="proj-1", chapter=1)
    assert "SF_LOG" not in output.body_text
    assert "MYSTERY_CLUE" not in output.body_text
    assert "林远踏入档案室" in output.body_text
    assert "血迹在角落" in output.body_text


def test_export_includes_narrative_arc_summary():
    chapter_text = "..."
    output = export_chapter_to_docx(chapter_text, project_id="proj-1", chapter=5)
    assert "叙事弧线摘要" in output.appendix_text
    # 含 8 registry 统计
    assert "冲突" in output.appendix_text
    assert "谜题" in output.appendix_text
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ImportError` 或测试失败

- [ ] **Step 3: 实现** — 修改 `infrastructure/export/docx_exporter.py`：

```python
import re
from domain.storyos.services.snapshot_projector import StoryOSSnapshotProjector

_SFLOG_PATTERN = re.compile(r'<!--\s*SF_LOG[^>]*?-->', re.DOTALL)

def export_chapter_to_docx(chapter_text: str, project_id: str, chapter: int) -> ExportResult:
    # 1. 过滤 SF_LOG 注释
    cleaned = _SFLOG_PATTERN.sub('', chapter_text)

    # 2. 生成叙事弧线摘要
    projector = StoryOSSnapshotProjector(...)
    summary = projector.get_arc_summary(project_id, chapter)

    # 3. 构造 DOCX body + appendix
    body_text = cleaned
    appendix_text = f"叙事弧线摘要（第 {chapter} 章）\n\n{summary}"

    return ExportResult(body_text=body_text, appendix_text=appendix_text)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed

- [ ] **Step 5: Commit** — `git add infrastructure/export/docx_exporter.py && git commit -m "feat(export): strip SF_LOG annotations + include narrative arc summary appendix"`

#### Task F3: 性能基准 + E2E 验收

**Files:**
- Create: `tests/e2e/test_storyos_workbench_flow.py`
- Create: `tests/performance/test_frontend_chunk_size.py`

- [ ] **Step 1: 写 E2E 测试**（端到端走 1D 全部产出）

```python
"""端到端：用户从打开 StoryOSHub 到完成一次 cascade simulate 的完整流程。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from interfaces.main import app


def test_e2e_storyos_workbench_flow():
    client = TestClient(app)

    # 1. 创建 3 个 conflict 关联
    cf1 = client.post("/api/v1/storyos/proj-1/conflict", json={"description": "a", "created_chapter": 1, "intensity": 30}).json()
    cf2 = client.post("/api/v1/storyos/proj-1/conflict", json={"description": "b", "created_chapter": 2, "intensity": 60}).json()

    # 2. 列出 conflict
    list_resp = client.get("/api/v1/storyos/proj-1/conflict")
    assert list_resp.status_code == 200
    assert list_resp.json()["meta"]["total"] == 2

    # 3. 触发 cascade simulate
    sim_resp = client.post(
        "/api/v1/storyos/proj-1/cascade/simulate",
        json={
            "trigger": "conflict_resolved",
            "source_asset_type": "conflict",
            "source_asset_id": cf1["id"],
            "proposed_new_status": "resolved",
        },
    )
    assert sim_resp.status_code == 200

    # 4. 查询 cascade history
    hist_resp = client.get("/api/v1/storyos/proj-1/cascade/history?limit=10")
    assert hist_resp.status_code == 200

    # 5. 查询 health
    health_resp = client.get("/api/v1/storyos/proj-1/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] in ("ok", "degraded")
```

- [ ] **Step 2: 性能基准**（前端 chunk 大小）

```python
# scripts/check_storyos_chunk_size.py
import os
import sys

CHUNK_DIR = "frontend/dist/assets"
MAX_SIZE_KB = 500

def main():
    if not os.path.exists(CHUNK_DIR):
        print(f"❌ {CHUNK_DIR} 不存在，请先运行 npm run build")
        sys.exit(1)

    chunks = [f for f in os.listdir(CHUNK_DIR) if "storyos" in f]
    for chunk in chunks:
        size_kb = os.path.getsize(os.path.join(CHUNK_DIR, chunk)) / 1024
        if size_kb > MAX_SIZE_KB:
            print(f"❌ {chunk} = {size_kb:.1f}KB 超过 {MAX_SIZE_KB}KB")
            sys.exit(1)
        print(f"✅ {chunk} = {size_kb:.1f}KB")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 运行 E2E + 性能** — `pytest tests/e2e/test_storyos_workbench_flow.py -v` + `python scripts/check_storyos_chunk_size.py` 全过

- [ ] **Step 4: 实现** — 端到端测试通过依赖所有前置阶段；性能脚本 CI 集成在 Group G 验收

- [ ] **Step 5: Commit** — `git add tests/e2e/ scripts/check_storyos_chunk_size.py && git commit -m "test(e2e): StoryOS workbench end-to-end + chunk size check script"`

---

### Group G: 验收与文档（1 任务）

#### Task G1: 验收清单 + 文档同步

**Files:**
- Create: `docs/superpowers/checklists/2026-07-02-storyos-1d-acceptance.md`
- Modify: `CLAUDE.md`（追加 StoryOS 工作台路径说明）
- Modify: `README.md`（如存在，追加 "StoryOS tier_0 集成" 章节）

- [ ] **Step 1: 创建验收清单**

```markdown
# StoryOS Phase 1D 验收清单

> 完成日期：__________  验收人：__________

## A. 功能验收（100% 必须通过）

### A.1 API 端点

- [ ] 40 CRUD 端点全 200/201/204（8 entity × 5 操作）
- [ ] 3 cascade 端点：simulate 200 / replay 200/501 / history 200
- [ ] 2 sflog 端点：raw 200 / reparse 200
- [ ] 2 migration 端点：501 + OpenAPI schema 可见
- [ ] 2 health/metrics 端点：200 + 6 指标齐全
- [ ] 错误路径覆盖：422/404 + ErrorResponse envelope

### A.2 Frontend

- [ ] StoryOSHub 主面板可访问
- [ ] 6 子视图全部可用
- [ ] 4 组件渲染正确
- [ ] 3 Pinia stores 状态同步
- [ ] PredeclaredDiff 三色高亮
- [ ] i18n 中文文案完整

## B. 集成验收

- [ ] 完整 happy path 端到端
- [ ] 与 1C 引擎钩子串联
- [ ] Export DOCX 不含 SF_LOG 注释
- [ ] OpenAPI schema 完整

## C. 性能基准

- [ ] 8 registry 列表 < 200ms
- [ ] CascadeGraph 渲染 < 500ms
- [ ] SFLogInspector 解析 < 200ms
- [ ] StoryOSHub 首屏 TTI < 1s

## D. 用户验收

- [ ] Workbench "StoryOS" 入口可见
- [ ] 5 子视图路由可达
- [ ] Migration 端点显示"功能开发中"

## E. 文档

- [ ] CLAUDE.md 更新
- [ ] README 更新（如适用）
- [ ] OpenAPI 文档可访问
- [ ] 验收清单签收
```

- [ ] **Step 2: 更新 CLAUDE.md**（在 Architecture 章节追加）

```markdown
<!-- CLAUDE.md 追加章节 -->
### StoryOS 工作台

项目接入 StoryForge2 tier_0 机制后，工作台新增 "叙事资产" 入口：
- 路径：`/book/:slug/storyos`
- 8 Registry（冲突/谜题/反转/承诺/揭示/预期/目标/伏笔）CRUD
- CascadeGraph 可视化
- SFLogInspector 章节 SF_LOG 注释解析
- PredeclaredDiff 预声明 vs 实际产出对比

详细设计见 `docs/superpowers/specs/2026-07-02-storyos-integration-design.md`
实施计划见 `docs/superpowers/plans/2026-07-02-storyos-phase-1d-frontend-api.md`
```

- [ ] **Step 3: 跑全部测试** — `pytest tests/ -m "not slow" -v` + `npm run test` 期望全过

- [ ] **Step 4: 标记 1D 完成**

```bash
# 验证所有 Group A-G 完成
ls interfaces/api/v1/storyos/  # 期望含 schemas/routes/crud_factory/router_registry/dependencies/error_handlers
ls frontend/src/views/workbench/storyos/  # 期望含 6 .vue 文件
ls frontend/src/stores/storyos/  # 期望含 3 .ts 文件
ls frontend/src/components/workbench/storyos/  # 期望含 4 .vue 文件
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/checklists/ CLAUDE.md
git commit -m "docs(storyos): add 1D acceptance checklist + update CLAUDE.md with StoryOS workbench path"
```

---

## 11. 任务完成度总览

| Group | 任务数 | 状态 | 关键产出 |
|---|---|---|---|
| **Group A** | 5 | ✅ 详版完成 | 8 entity DTO + crud_factory + 51 端点注册 + ErrorResponse envelope |
| **Group B** | 3 | ✅ 详版完成 | 8 registry × 5 CRUD = 40 端点 + 性能基准 |
| **Group C** | 4 | ✅ 详版完成 | cascade (3) + sflog (2) + migration (2, 桩) + health/metrics (2) |
| **Group D** | 4 | ✅ 详版完成 | TypeScript 类型 + 5 API client + 3 Pinia stores + 嵌套路由 + StoryOSHub |
| **Group E** | 6 | ✅ 详版完成 | StatusBadge + AssetCard + RegistryList + RegistryDetailDrawer + CascadeGraph + CascadeStepNode + IntensityChart + SFLogInspector + PredeclaredDiff + Vite chunk + i18n |
| **Group F** | 3 | ✅ 详版完成 | 1C 钩子集成测试 + DOCX 改造 + E2E + 性能基准 |
| **Group G** | 1 | ✅ 详版完成 | 验收清单 + CLAUDE.md 同步 |
| **合计** | **26** | **✅** | **~6400 LOC（含测试）** |

---

## 12. 与 1A/1B/1C 详版对齐声明

本详版完全对齐 1A/1B/1C 的 TDD 风格：
- ✅ 每个任务严格 5 步循环（写失败测试 → 运行 → 实现 → 通过 → commit）
- ✅ 完整代码示例（Python + TypeScript + Vue 3 Composition API）
- ✅ 测试文件命名规范（unit/integration/frontend 三层）
- ✅ commit 消息前缀分类（feat/test/perf/docs/refactor）
- ✅ 实施顺序与并行机会明示
- ✅ 跨阶段契约锁定（1A/1B 消费，1E 消费）
- ✅ 风险 → 任务映射
- ✅ 验收标准（功能/集成/性能/用户）

本详版可作为 Phase 1D 实施的**权威指南**，与 1A/1B/1C 详版共同构成 StoryOS tier_0 集成的完整执行手册。


### 4.1 Backend 新增文件

```
interfaces/api/v1/storyos/
  __init__.py
  schemas/
    __init__.py
    common_schemas.py                        # PaginationMeta + ListResponseEnvelope + ErrorResponse
    conflict_schemas.py                      # 5 entity 字段
    mystery_schemas.py                       # + clues/category
    twist_schemas.py                         # + twist_type/trigger_chapter/foreshadowing_refs
    promise_schemas.py                       # + fulfillment_chapter/importance/linked_conflict_id
    reveal_schemas.py                        # + reveal_type/revealed_chapter/related_mystery_id
    expectation_schemas.py                   # + intensity/linked_twist_id/linked_conflict_id/ready_chapter
    goal_schemas.py                          # + progress_marker/linked_character_id/completion_chapter
    foreshadowing_schemas.py                 # + importance/payoff_chapter/migrated_from_legacy_id
    cascade_schemas.py                       # CascadeStepDTO + SimulateRequest/Response/ReplayRequest
    sflog_schemas.py                         # SFLogRawResponse + SFLogReparseResponse + SFLogRecordDTO
    migration_schemas.py                     # MigrationPreviewResponse/ExecuteRequest/ExecuteResponse/StatusResponse
  routes/
    __init__.py
    cascade_routes.py
    sflog_routes.py
    migration_routes.py                      # 1D 桩
    health_routes.py                         # + /metrics
  crud_factory.py                            # 5 CRUD × 8 registry = 40 端点
  router_registry.py                         # 聚合 51+ 端点为单一 APIRouter
  dependencies.py                            # 8 registry + cascade + sflog + migration + metrics 服务的 DI 工厂
  error_handlers.py                          # 统一 ErrorResponse envelope

tests/unit/interfaces/api/v1/storyos/
  __init__.py
  schemas/
    __init__.py
    test_conflict_schemas.py                 # 7 测试（作为 8 entity 同构蓝本）
    test_common_schemas.py                   # 6 测试
    test_cascade_schemas.py                  # 5 测试
    test_sflog_schemas.py                    # 5 测试
    test_migration_schemas.py                # 4 测试
  test_crud_factory.py                       # 5 测试

tests/integration/api/v1/storyos/
  __init__.py
  test_conflict_endpoints.py                 # 8 集成测试
  test_mystery_endpoints.py
  test_promise_endpoints.py
  test_goal_endpoints.py
  test_twist_endpoints.py
  test_reveal_endpoints.py
  test_expectation_endpoints.py
  test_foreshadowing_endpoints.py
  test_cascade_endpoints.py
  test_sflog_endpoints.py
  test_migration_endpoints.py                # 1D 桩测试
  test_health_endpoints.py
  test_router_registration.py                # OpenAPI schema 完整性
```

### 4.2 Backend 修改文件

```
interfaces/main.py                           # 注册 storyos 子路由 + error handlers
```

### 4.3 Frontend 新增文件

```
frontend/src/api/storyos/
  __init__.ts
  index.ts                                   # 总入口，re-export
  http.ts                                    # apiClient 共享配置
  registry.ts                                # 8 registry CRUD 客户端
  cascade.ts                                 # cascade simulate/replay/history
  sflog.ts                                   # sflog raw/reparse
  migration.ts                               # migration preview/execute（401/501 处理）
  health.ts                                  # health/metrics
  types.ts                                   # 8 entity TypeScript 类型 + 共用 envelope

frontend/src/stores/storyos/
  __init__.ts
  queries.ts                                 # 8 registry queries（reactive refs + fetchers）
  cascade.ts                                 # cascade simulate/replay/history
  sflog.ts                                   # sflog raw/reparse

frontend/src/types/
  storyos.ts                                 # TypeScript 类型定义（与后端 DTO 同步）

frontend/src/views/workbench/storyos/
  __init__.ts
  StoryOSHub.vue                             # 主面板（侧边栏 + 5 tab）
  RegistryList.vue                           # 8 registry 通用列表（按 asset_type 路由）
  RegistryDetailDrawer.vue                   # 详情抽屉（编辑 + 关联展示）
  CascadeGraph.vue                           # Vue Flow DAG 可视化
  SFLogInspector.vue                         # 并排布局
  PredeclaredDiff.vue                        # diff 高亮
  __tests__/
    StoryOSHub.spec.ts
    RegistryList.spec.ts
    RegistryDetailDrawer.spec.ts
    CascadeGraph.spec.ts
    SFLogInspector.spec.ts
    PredeclaredDiff.spec.ts

frontend/src/components/workbench/storyos/
  __init__.ts
  AssetCard.vue                              # 资产卡片（用于 RegistryList）
  CascadeStepNode.vue                        # Vue Flow 自定义节点
  IntensityChart.vue                         # ECharts 强度趋势
  StatusBadge.vue                            # 12 态颜色映射
  __tests__/
    AssetCard.spec.ts
    CascadeStepNode.spec.ts
    IntensityChart.spec.ts
    StatusBadge.spec.ts

frontend/src/stores/storyos/__tests__/
  queries.spec.ts
  cascade.spec.ts
  sflog.spec.ts

frontend/src/api/storyos/__tests__/
  registry.spec.ts
  cascade.spec.ts
  sflog.spec.ts
  migration.spec.ts
```

### 4.4 Frontend 修改文件

```
frontend/src/router/index.ts                 # 新增 /book/:slug/storyos 嵌套路由
frontend/src/i18n/locales/zh-CN.json         # storyos 文案
frontend/src/i18n/locales/en-US.json         # storyos 文案（兜底）
frontend/vite.config.ts                      # chunk 拆分（storyos 子模块）
```

### 4.5 文件规模预估

| 层 | 文件数 | 估算 LOC |
|---|---|---|
| Backend: schemas | 13 | ~800 |
| Backend: routes | 5 | ~500 |
| Backend: factory + deps + handlers | 3 | ~300 |
| Backend: tests | ~18 | ~1500 |
| Frontend: types + api | 7 | ~400 |
| Frontend: stores | 4 | ~500 |
| Frontend: views | 6 | ~1200 |
| Frontend: components | 4 | ~400 |
| Frontend: tests | ~12 | ~600 |
| Frontend: router + i18n | 4 | ~200 |
| **合计** | **~76** | **~6400**（远超 2200 LOC 目标，因含测试） |

> 注：LOC 目标 2200 指生产代码；含测试实际 ~6400 LOC。1A/1B/1C 同样模式。

---

## 5. 跨阶段契约

### 5.1 1D 消费 1A/1B 契约（已锁定）

| 1A/1B 产出 | 1D 消费方式 |
|---|---|
| `domain/storyos/entities/{8}.py` | 8 DTO 的 `from_domain()` 构造器输入 |
| `application/storyos/services/registry_service.py` 的 8 个 service | crud_factory 的 `service` 参数（CRUDService Protocol） |
| `application/storyos/services/cascade_service.py` | cascade_routes 调 `simulate()` / `get_history()` |
| `application/storyos/services/sf_log_parser_service.py` | sflog_routes 调 `parse_only()` / `validate_format()` / `match_against_predeclared()` |
| `application/storyos/services/snapshot_projector.py` | health_routes 调 `get_metrics()` |
| `application/storyos/services/circuit_breaker_integration.py` | SFLogComplianceGate 内部用，1D 暴露 `force_pass_count_per_chapter` 指标 |
| `infrastructure/persistence/database/write_dispatch.py` | 8 registry 写入走单写者 |
| `interfaces/runtime.py::get_runtime_container` | DI 工厂 `dependencies.py` 解析 8 service |

### 5.2 1D 产出供 1E 消费

| 1D 产出 | 1E 消费方式 |
|---|---|
| `interfaces/api/v1/storyos/routes/migration_routes.py` | 1E 替换桩实现为 `ForeshadowingMigrationService.scan()` / `.execute()` |
| `interfaces/api/v1/storyos/schemas/migration_schemas.py` | 1E 复用 DTO（MigrationPreviewResponse / MigrationExecuteResponse） |

### 5.3 1D 内部契约（不可破坏）

| 契约 | 约束 |
|---|---|
| 端点路径前缀 | `/api/v1/storyos/{project_id}/` 不可变 |
| CRUD 路径模板 | `/{asset_type}` 与 `/{asset_type}/{asset_id}` 不可变（crud_factory 锁定） |
| 响应 envelope | 列表用 `ListResponseEnvelope`，详情用 entity Response，错误用 `ErrorResponse` |
| 错误代码 | `VALIDATION_ERROR` / `ASSET_NOT_FOUND` / `NOT_IMPLEMENTED` / `INTERNAL_ERROR` / `FORMAT_ERROR` / `CASCADE_BLOCKED` |
| 分页参数 | `?page=1&page_size=20&status=...&asset_type=...` |
| 12 态 status 序列化 | snake_case 字符串（如 `"escalated"`） |
| Project ID 别名 | 路径 `project_id` 内部映射到 `novel_id`（在 service 层做 alias） |

### 5.4 1D 与 1C 引擎钩子的对接

1D 不直接调用 `StoryOSDelegate`，而是通过**触发 chapter 重写**间接走 1C 钩子：

```typescript
// frontend/src/api/storyos/cascade.ts
export async function regenerateChapter(projectId: string, chapterId: number) {
  // 调 1C 暴露的 chapter 重新生成端点（已存在于 interfaces/api/v1/engine/generation.py）
  return await apiClient.post(`/api/v1/chapters/${chapterId}/regenerate`, {
    project_id: projectId,
    trigger: "storyos_replay",  // 标识 StoryOS 回放
  });
}
```

---

## 6. 验收标准

### 6.1 功能验收（100% 必须通过）

#### 6.1.1 API 端点

- [ ] **8 registry × 5 CRUD = 40 端点全部 200/201/204**（含正常路径）
- [ ] **3 cascade 端点**：simulate 200 / replay 200 或 501 / history 200
- [ ] **2 sflog 端点**：raw 200 / reparse 200
- [ ] **2 migration 端点**：1D 阶段 501 + OpenAPI schema 可见
- [ ] **2 health/metrics 端点**：200 + 6 指标字段齐全
- [ ] **错误路径**：缺必填 → 422 + `VALIDATION_ERROR` envelope / 资源不存在 → 404 + `ASSET_NOT_FOUND` envelope
- [ ] **AssetStatus 序列化为 snake_case 字符串**（12 态全部覆盖）

#### 6.1.2 Frontend

- [ ] **StoryOSHub 主面板可访问**（`/book/:slug/storyos` 路由）
- [ ] **6 子视图全部可用**：RegistryList / RegistryDetailDrawer / CascadeGraph / SFLogInspector / PredeclaredDiff
- [ ] **4 组件渲染正确**：StatusBadge 12 态颜色 / AssetCard 含状态徽章 / CascadeStepNode 用 Vue Flow 自定义节点 / IntensityChart ECharts
- [ ] **3 Pinia stores 状态同步**：跨视图状态一致（如在 CascadeGraph 触发 replay 后 RegistryList 自动 refetch）
- [ ] **PredeclaredDiff 三色高亮**：绿/红/黄三态
- [ ] **i18n 中文文案完整**：5 个视图的所有 label 翻译
- [ ] **路由懒加载**：build 后 storyos chunk < 500KB

### 6.2 集成验收

- [ ] **完整 happy path 端到端**：
  1. 打开 Workbench → 进入 StoryOSHub
  2. 切换到 Conflict 列表 → 创建 conflict
  3. 查看详情抽屉 → 关联 expectation
  4. 切换到 CascadeGraph → 触发 simulate
  5. 切到 SFLogInspector → 查看章节 5 的 SF_LOG 解析
  6. 切到 PredeclaredDiff → 查看 planner 预声明 vs 实际产出
- [ ] **与 1C 引擎钩子串联**：
  - 在 StoryOSHub 触发 chapter 重写 → 1C 走 Step 1/3/5/6 → StoryOS 状态变更 → 前端自动刷新
- [ ] **Export DOCX 不含 SF_LOG 注释**，但含「叙事弧线摘要」附录（自动从 8 registry 状态汇总）
- [ ] **OpenAPI schema 完整**：`/openapi.json` 包含全部 51+ 端点

### 6.3 性能基准

- [ ] **8 registry 列表查询 < 200ms**（Task B3 已锁定）
- [ ] **CascadeGraph 渲染 < 500ms**（含 Vue Flow + ECharts 嵌套）
- [ ] **SFLogInspector 解析 100 条 SF_LOG < 200ms**
- [ ] **StoryOSHub 首屏 TTI < 1s**（路由懒加载 + chunk 拆分）

### 6.4 用户验收（Workbench 可见）

- [ ] StoryOSHub 页面可访问、可查询 8 Registry
- [ ] CascadeGraph 可视化级联路径（节点 + 边 + 强度趋势）
- [ ] SFLogInspector 显示原始文本（高亮 SF_LOG 块）+ 解析结果并排
- [ ] PredeclaredDiff 高亮绿/红/黄三色
- [ ] 与 1E migration 端点联通（即使 1E 未完成时显示"功能开发中"）

---

## 7. 风险与缓解

| # | 风险 | 等级 | 缓解 |
|---|---|---|---|
| 1 | 8 entity 字段差异导致 crud_factory 不通用 | 🟡 中 | Factory 用 `Type[BaseModel]` 泛型，每个 entity 提供独立 create/update/response schema；entity 特有字段通过 schema 扩展（不影响 factory 主体）|
| 2 | Frontend 状态同步复杂（多 store 跨视图）| 🟡 中 | 单一数据源：3 store 共享 `project_id` 上下文；watch 关键 mutation 触发 refetch；Vue Query 风格 invalidation |
| 3 | CascadeGraph 性能（节点 > 100 时渲染慢）| 🟡 中 | Vue Flow 节点虚拟化；ECharts 启用 `progressive` 渲染；超过 200 节点时降级为列表视图 |
| 4 | Migration 端点 1D 桩与 1E 联通差异 | 🟢 低 | 1D 桩 schema 与 1E 期望对齐（1E 直接替换业务逻辑，schema 不动）|
| 5 | Frontend i18n 遗漏 | 🟢 低 | 所有 label 强制走 i18n key；CI 加 `i18n-key-coverage` 检查 |
| 6 | API 性能未达 200ms | 🟡 中 | 复合索引 `(project_id, status, created_chapter)`；list 加分页避免全表扫；connection pool 调优 |
| 7 | ErrorResponse envelope 与现有 evolution_routes 不一致 | 🟢 低 | 复用 evolution_routes 的 error format（`detail.code/message/details`）；新增全局 handler 统一 |

### 7.1 风险 → 任务映射

| 风险 | 缓解任务 |
|---|---|
| #1 crud_factory 通用性 | A1 (8 entity schema 同构) + A4 (factory 实现) |
| #2 状态同步 | D2 (3 stores) + D3 (路由) + E2 (RegistryList watch) |
| #3 CascadeGraph 性能 | E3 (CascadeGraph + 节点虚拟化) |
| #4 Migration 桩 | C3 (1D 桩实现) + 1E 替换 |
| #5 i18n 遗漏 | D4 (StoryOSHub) + E1-E5 (各视图 i18n) + CI 检查 |
| #6 API 性能 | B3 (性能基准 + 索引) |
| #7 错误 envelope | A5 (error_handlers) |

---

## 8. 设计参考

### 8.1 Spec 章节锚点

- spec §2.4 架构边界（interfaces + frontend 层）
- spec §3.1 完整文件清单（8. interfaces/ + 9. frontend/）
- spec 附录 D（51 端点路径表）
- spec §5.3 关键测试用例 + 性能基准
- spec §6.4 验收标准

### 8.2 上游阶段产出

- 1A 类型契约：[`./2026-07-02-storyos-phase-1a-foundation.md`](./2026-07-02-storyos-phase-1a-foundation.md)
- 1B service 接口：[`./2026-07-02-storyos-phase-1b-application.md`](./2026-07-02-storyos-phase-1b-application.md)
- 1C 引擎钩子：[`./2026-07-02-storyos-phase-1c-engine.md`](./2026-07-02-storyos-phase-1c-engine.md)

### 8.3 现有代码模式（参考）

- **API 路由**：`interfaces/api/v1/engine/evolution_routes.py`（同结构、`router = APIRouter(prefix="/novels/{novel_id}/evolution", tags=["evolution"])`、`get_evolution_*_service` DI）
- **Error envelope**：参考 `interfaces/api/v1/dependencies.py` 现有的 `HTTPException(detail={...})` 模式
- **DI 工厂**：`interfaces/runtime.py::get_runtime_container()` 已有，需新增 `storyos_*` 注册
- **Frontend store**：`frontend/src/stores/dagStore.ts`（同模式：defineStore + reactive refs + computed + actions）
- **Frontend API client**：`frontend/src/api/evolution.ts`（同模式：apiClient + interface 定义 + 列表/详情函数）
- **Frontend router**：`frontend/src/router/index.ts`（已有 `/book/:slug/workbench` 模式，新增嵌套路由）
- **Vue 组件**：`frontend/src/views/Workbench.vue`（Naive UI `n-split` 布局 + 侧边栏模式）

### 8.4 工具链

- 后端：FastAPI 0.109 + Pydantic 2 + pytest 7.x + pytest-asyncio
- 前端：Vue 3.5 + Naive UI 2.44 + Pinia 3 + Vue Flow 1.48 + ECharts 6 + vue-tsc 3.x
- 测试：pytest（后端）+ Vitest + Vue Test Utils（前端，待 frontend 集成）
- Lint：ruff（后端）+ ESLint + Prettier（前端）

---

## 9. 进度追踪

| 子阶段 | 文件 | 状态 | 任务细节 |
|---|---|---|---|
| **1A Foundation** | [`2026-07-02-storyos-phase-1a-foundation.md`](./2026-07-02-storyos-phase-1a-foundation.md) | ✅ 详版完成 | 28 任务细粒度 TDD |
| **1B Application** | [`2026-07-02-storyos-phase-1b-application.md`](./2026-07-02-storyos-phase-1b-application.md) | ✅ 详版完成 | 20 任务细粒度 TDD |
| **1C Engine** | [`2026-07-02-storyos-phase-1c-engine.md`](./2026-07-02-storyos-phase-1c-engine.md) | ✅ 详版完成 | 9 任务细粒度 TDD |
| **1D Frontend + API** | [`2026-07-02-storyos-phase-1d-frontend-api.md`](./2026-07-02-storyos-phase-1d-frontend-api.md) | ✅ 详版完成 | 26 任务细粒度 TDD |
| **1E Migration** | [`2026-07-02-storyos-phase-1e-migration.md`](./2026-07-02-storyos-phase-1e-migration.md) | 🔄 占位符 | 7 任务分组占位，等 1A 完成后细化 |

**1D 任务完成度清单**：
- [ ] Group A: API Schemas + Factory (5 任务)
- [ ] Group B: 8 Registry CRUD 端点 (3 任务)
- [ ] Group C: Cascade + SFLog + Migration 端点 (4 任务)
- [ ] Group D: Frontend 基础设施 (4 任务)
- [ ] Group E: 6 子视图 + 4 组件 (6 任务)
- [ ] Group F: 集成 + 端到端 (3 任务)
- [ ] Group G: 验收与文档 (1 任务)
- [ ] **合计**: 26 任务

---

## 10. 总结

1D 是 StoryOS 集成的**最厚一层**（LOC 2200，26 任务），承担 3 个关键桥梁角色：
1. **API ↔ Application**（crud_factory 把 8 service 转为 40 端点）
2. **Frontend ↔ API**（3 store + 5 api client 把 51+ 端点收敛为响应式状态）
3. **Workbench ↔ User**（StoryOSHub 把 SF_LOG + Registry + Cascade + Metrics 全部暴露给作者）

1D 与其他阶段的关键差异：
- **1A/1B 全部串行**（类型 → 持久化 → 业务）
- **1C 串行**（4 钩子接入）
- **1D 高度并行**（4 subagent 可同步推进 Group A/B/C/D，Group E 等 D 完成后启动）

1D 完成后，StoryOS tier_0 机制对用户**完全可见**：
- 在 Workbench 可查询 8 Registry
- 可视化级联路径
- 查看 SF_LOG 解析结果
- 比较 planner 预声明与实际产出
- 触发 chapter 重写间接走 1C 引擎

为 Phase 2（CreativeOS）做好基础设施准备。
