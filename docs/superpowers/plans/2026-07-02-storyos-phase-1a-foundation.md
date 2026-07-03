# StoryOS Phase 1A — Foundation 实施计划（详版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Parent Plan:** [`2026-07-02-storyos-integration.md`](./2026-07-02-storyos-integration.md)
**Spec Reference:** [`../specs/2026-07-02-storyos-integration-design.md`](../specs/2026-07-02-storyos-integration-design.md) §3.1, §3.2, §3.4, §3.5, 附录 C
**Sub-Spec Reference:** [`../specs/2026-07-02-storyos-asset-field-spec.md`](../specs/2026-07-02-storyos-asset-field-spec.md) §1 SFLogRecord, §2 TwistType, §3 Clue
**Phase Scope:** Domain layer + Persistence layer + WriteDispatch 扩展 + 迁移脚手架
**LOC Target:** ~3000
**Estimated Tasks:** 28
**Estimated Duration:** 1 周

---

## 0. 前置条件

```bash
# 1. 确认 Python 路径与项目根
cd /Users/longsa/Codes/plotPilot
python -c "import sys; print(sys.version)"  # 期望 3.11+

# 2. 确认 pytest 可用
pytest --version  # 期望 7.x+

# 3. 确认 SQLAlchemy / Pydantic 已安装
python -c "import sqlalchemy, pydantic; print(sqlalchemy.__version__, pydantic.VERSION)"
# 期望 SQLAlchemy 2.x + Pydantic 2.x

# 4. 确认 alembic 已安装
alembic --version  # 期望 1.x+
```

---

## 1. 阶段目标

建立 StoryOS bounded context 的**类型地基**与**持久化基础设施**，使后续 1B/1C/1D 阶段可以无障碍地引用类型契约与持久化原语。

### 1.1 产出物清单

- `domain/storyos/` 完整子包（contracts + 4 value_objects + 8 entities + `__init__.py`）
- `infrastructure/persistence/storyos/` 完整 schemas + mappers（11 张表 + ORM）
- `infrastructure/persistence/database/write_dispatch.py` 新增 `WriteTransaction` 类 + `WriteDispatch.transaction()` + `queue_apply()`
- Alembic 迁移：`infrastructure/persistence/database/migrations/versions/0001_storyos_init.py`
- 脚手架：`scripts/migrate_storyos.py`（**仅 CLI 骨架，完整实现在 1E**）

### 1.2 关键契约锁定

| 契约 | 消费者 | 任务编号 |
|---|---|---|
| `AssetStatus` (12 态) + `FORBIDDEN_TRANSITIONS` | 1B services, 1C 引擎 | A1, A4 |
| `SFLogType` (11 类) | 1B parsers | A2 |
| `CascadeTrigger` (6 类) | 1B cascade_service | A3 |
| `SFLogRecord` (6 字段，sub-spec §1) | 1B parsers | B1 |
| `Clue` (9 字段 + ClueCategory，sub-spec §3) | 1B MysteryService | C2 |
| `TwistType` (6 值，sub-spec §2) | 1B cascade_service | C3 |
| `WriteTransaction` + `transaction()` + `queue_apply()` | 1B bridge_service | D1, D2, D3 |
| 11 张表 schema | 1B/1D 仓储 | E1, E2, E3 |

### 1.3 不在本阶段范围

- ❌ SF_LOG 正则解析器（→ 1B `parsers/`）
- ❌ 8 Registry 的 Service/Repository 业务逻辑（→ 1B）
- ❌ Cascade 业务执行（→ 1B `cascade_service`）
- ❌ EvolutionBridge 双写业务（→ 1B `evolution_bridge_service`）
- ❌ StoryOSDelegate 引擎钩子（→ 1C）
- ❌ API 端点（→ 1D）
- ❌ 旧 Foreshadowing 数据迁移逻辑（→ 1E，仅留脚手架）
- ❌ `Clue.to_revealed_clue_item()` 投影方法（→ 1B MysteryService，DDD 分层要求 domain 不依赖 application）

---

## 2. TDD 约定

每个任务严格遵循 5 步循环（2-5 分钟/步）：

1. **写失败测试**：在 `tests/unit/...` 创建测试文件，先写最关键行为的断言
2. **运行测试确认失败**：期望 `ImportError` / `AttributeError` / `AssertionError`
3. **写最小实现**：在指定实现文件创建骨架，刚好让测试通过
4. **运行测试确认通过**：期望 PASS
5. **Commit**：`git add ... && git commit -m "..."`

### 2.1 通用 commit 消息前缀

- `feat(domain):` — 领域类型新增
- `feat(persistence):` — ORM/Mapper/Schema
- `feat(write-dispatch):` — WriteDispatch 扩展
- `feat(migration):` — 迁移脚本
- `feat(scripts):` — 脚手架脚本
- `test(domain):` / `test(persistence):` — 纯测试补充
- `docs(persistence):` — 约定文档

### 2.2 测试文件命名

- Domain 实体/值对象：`tests/unit/domain/storyos/{value_objects,entities}/test_<name>.py`
- Persistence schema：`tests/unit/infrastructure/persistence/storyos/schemas/test_<name>_schema.py`
- Persistence mapper：`tests/unit/infrastructure/persistence/storyos/mappers/test_<name>_mapper.py`
- WriteDispatch 扩展：`tests/unit/infrastructure/persistence/database/test_write_dispatch_transaction.py`

### 2.3 实施顺序与并行机会

**严格顺序依赖**：
- Group A → Group B（值对象引用枚举）
- Group B → Group C（实体引用值对象）
- Group C → Group E（schema 引用实体）
- Group D 与 A/B/C 并行（独立）
- Group E → Group F（迁移引用 schema）

**可并行**：
- Group A/B/C/D 内部任务可并行（无跨组依赖）
- Group E 的 3 个任务可并行（独立文件）

---

## 3. 任务清单

---

### Group A: Domain Contracts & Enums（5 任务）

#### Task A1: AssetStatus 枚举（12 态）

**Files:**
- Create: `domain/storyos/__init__.py`（**新增**：子包标记，A1 落地时建立）
- Create: `domain/storyos/contracts.py`
- Create: `tests/unit/domain/storyos/test_asset_status.py`

- [ ] **Step 1: 写失败测试** — `tests/unit/domain/storyos/test_asset_status.py`

```python
import re
from domain.storyos.contracts import AssetStatus


def test_asset_status_has_12_members():
    assert len(AssetStatus) == 12


def test_asset_status_member_values():
    expected = {
        "ACTIVE", "ACCUMULATING", "PLANTED", "DEVELOPING",
        "HIDDEN", "READY_TO_FULFILL", "ESCALATED", "REVEALED",
        "FULFILLED", "RESOLVED", "ABANDONED", "DEAD",
    }
    actual = {m.name for m in AssetStatus}
    assert actual == expected


def test_asset_status_values_are_snake_case_strings():
    pattern = re.compile(r"^[a-z_]+$")
    for m in AssetStatus:
        assert pattern.match(m.value), f"{m.name}={m.value!r} not snake_case"


def test_asset_status_is_string_enum():
    assert isinstance(AssetStatus.ACTIVE, str)
    assert AssetStatus.ACTIVE == "active"
    assert AssetStatus.ACTIVE.value == "active"
```

- [ ] **Step 2: 运行测试确认失败** — `pytest tests/unit/domain/storyos/test_asset_status.py -v` 期望 `ModuleNotFoundError: No module named 'domain.storyos'`
- [ ] **Step 3: 写最小实现** — 创建 `domain/storyos/__init__.py`（空文件） + `domain/storyos/contracts.py`：

```python
"""StoryOS bounded context 的契约层（枚举 + 协议 + 常量）。"""
from __future__ import annotations

from enum import Enum


class AssetStatus(str, Enum):
    """narrative asset 的生命周期状态（spec §3.2 锁定 12 态）。"""

    ACTIVE = "active"
    ACCUMULATING = "accumulating"
    PLANTED = "planted"
    DEVELOPING = "developing"
    HIDDEN = "hidden"
    READY_TO_FULFILL = "ready_to_fulfill"
    ESCALATED = "escalated"
    REVEALED = "revealed"
    FULFILLED = "fulfilled"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"
    DEAD = "dead"
```

- [ ] **Step 4: 运行测试确认通过** — `pytest tests/unit/domain/storyos/test_asset_status.py -v` 期望 4 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/ tests/unit/domain/storyos/test_asset_status.py && git commit -m "feat(domain): scaffold storyos/ subpackage + add AssetStatus enum with 12 states"`

#### Task A2: SFLogType 枚举（11 类）

**Files:**
- Modify: `domain/storyos/contracts.py`（追加）
- Create: `tests/unit/domain/storyos/test_sflog_type.py`

- [ ] **Step 1: 写失败测试**

```python
from domain.storyos.contracts import SFLogType, RELATIONAL_LOG_TYPES


def test_sflog_type_has_11_members():
    assert len(SFLogType) == 11


def test_sflog_type_member_names():
    expected = {
        "CHARACTER_EMOTION", "CHARACTER_RELATION_CHANGE", "CHARACTER_LOCATION_CHANGE",
        "CHARACTER_PHYSICAL_CHANGE", "KNOWLEDGE_GAIN", "CONFLICT_ESCALATE",
        "MYSTERY_CLUE", "TWIST_REVEAL", "EXPECTATION_FULFILL",
        "GOAL_MILESTONE", "REGISTRY_CREATE",
    }
    assert {m.name for m in SFLogType} == expected


def test_sflog_type_values_are_snake_case():
    for m in SFLogType:
        assert m.value == m.name.lower().replace("_", "_")  # sanity


def test_relational_log_types_constant():
    assert isinstance(RELATIONAL_LOG_TYPES, frozenset)
    assert SFLogType.CHARACTER_RELATION_CHANGE in RELATIONAL_LOG_TYPES
    assert len(RELATIONAL_LOG_TYPES) == 1
    assert SFLogType.MYSTERY_CLUE not in RELATIONAL_LOG_TYPES
```

- [ ] **Step 2: 运行测试确认失败** — `pytest tests/unit/domain/storyos/test_sflog_type.py -v` 期望 `ImportError: cannot import name 'SFLogType'`
- [ ] **Step 3: 实现** — 在 `domain/storyos/contracts.py` 追加：

```python
class SFLogType(str, Enum):
    """章节文本中 SF_LOG 注释的语义分类（spec 附录 A 锁定 11 类）。"""

    CHARACTER_EMOTION = "character_emotion"
    CHARACTER_RELATION_CHANGE = "character_relation_change"
    CHARACTER_LOCATION_CHANGE = "character_location_change"
    CHARACTER_PHYSICAL_CHANGE = "character_physical_change"
    KNOWLEDGE_GAIN = "knowledge_gain"
    CONFLICT_ESCALATE = "conflict_escalate"
    MYSTERY_CLUE = "mystery_clue"
    TWIST_REVEAL = "twist_reveal"
    EXPECTATION_FULFILL = "expectation_fulfill"
    GOAL_MILESTONE = "goal_milestone"
    REGISTRY_CREATE = "registry_create"


RELATIONAL_LOG_TYPES = frozenset(
    {
        SFLogType.CHARACTER_RELATION_CHANGE,
    }
)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/contracts.py tests/unit/domain/storyos/test_sflog_type.py && git commit -m "feat(domain): add SFLogType enum with 11 categories + RELATIONAL_LOG_TYPES"`

#### Task A3: CascadeTrigger 枚举（6 类）

**Files:**
- Modify: `domain/storyos/contracts.py`（追加）
- Create: `tests/unit/domain/storyos/test_cascade_trigger.py`

- [ ] **Step 1: 写失败测试**

```python
from domain.storyos.contracts import CascadeTrigger


def test_cascade_trigger_has_6_members():
    assert len(CascadeTrigger) == 6


def test_cascade_trigger_member_names():
    expected = {
        "MYSTERY_REVEALED", "TWIST_REVEALED", "REVEAL_REVEALED",
        "PROMISE_FULFILLED", "CONFLICT_RESOLVED", "CONFLICT_ESCALATED",
    }
    assert {m.name for m in CascadeTrigger} == expected


def test_conflict_escalated_exists():
    assert CascadeTrigger.CONFLICT_ESCALATED.value == "conflict_escalated"
```

- [ ] **Step 2: 运行测试确认失败** — `pytest tests/unit/domain/storyos/test_cascade_trigger.py -v` 期望 `ImportError`
- [ ] **Step 3: 实现** — 在 `domain/storyos/contracts.py` 追加：

```python
class CascadeTrigger(str, Enum):
    """级联触发的语义分类（spec §3.2 锁定 6 类）。"""

    MYSTERY_REVEALED = "mystery_revealed"
    TWIST_REVEALED = "twist_revealed"
    REVEAL_REVEALED = "reveal_revealed"
    PROMISE_FULFILLED = "promise_fulfilled"
    CONFLICT_RESOLVED = "conflict_resolved"
    CONFLICT_ESCALATED = "conflict_escalated"
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/contracts.py tests/unit/domain/storyos/test_cascade_trigger.py && git commit -m "feat(domain): add CascadeTrigger enum with CONFLICT_ESCALATED"`

#### Task A4: FORBIDDEN_TRANSITIONS + is_forbidden_transition

**Files:**
- Modify: `domain/storyos/contracts.py`（追加）
- Create: `tests/unit/domain/storyos/test_forbidden_transitions.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from domain.storyos.contracts import (
    AssetStatus, FORBIDDEN_TRANSITIONS, is_forbidden_transition,
)


def test_forbidden_transitions_count():
    assert len(FORBIDDEN_TRANSITIONS) == 8


def test_forbidden_transitions_contents():
    expected = {
        (AssetStatus.RESOLVED, AssetStatus.ACTIVE),
        (AssetStatus.FULFILLED, AssetStatus.ACTIVE),
        (AssetStatus.REVEALED, AssetStatus.HIDDEN),
        (AssetStatus.DEAD, AssetStatus.ACTIVE),
        (AssetStatus.ABANDONED, AssetStatus.PLANTED),
        (AssetStatus.ABANDONED, AssetStatus.DEVELOPING),
        (AssetStatus.RESOLVED, AssetStatus.PLANTED),
        (AssetStatus.FULFILLED, AssetStatus.PLANTED),
    }
    assert FORBIDDEN_TRANSITIONS == expected


@pytest.mark.parametrize("src,dst,expected", [
    (AssetStatus.RESOLVED, AssetStatus.ACTIVE, True),
    (AssetStatus.ACTIVE, AssetStatus.RESOLVED, False),
    (AssetStatus.DEAD, AssetStatus.ACTIVE, True),
    (AssetStatus.ACTIVE, AssetStatus.PLANTED, False),
])
def test_is_forbidden_transition(src, dst, expected):
    assert is_forbidden_transition(src, dst) is expected


def test_is_forbidden_transition_type_validation():
    with pytest.raises(TypeError):
        is_forbidden_transition("active", AssetStatus.ACTIVE)
```

- [ ] **Step 2: 运行测试确认失败** — `pytest tests/unit/domain/storyos/test_forbidden_transitions.py -v` 期望 `ImportError`
- [ ] **Step 3: 实现** — 在 `domain/storyos/contracts.py` 追加：

```python
FORBIDDEN_TRANSITIONS: frozenset[tuple[AssetStatus, AssetStatus]] = frozenset({
    (AssetStatus.RESOLVED, AssetStatus.ACTIVE),
    (AssetStatus.FULFILLED, AssetStatus.ACTIVE),
    (AssetStatus.REVEALED, AssetStatus.HIDDEN),
    (AssetStatus.DEAD, AssetStatus.ACTIVE),
    (AssetStatus.ABANDONED, AssetStatus.PLANTED),
    (AssetStatus.ABANDONED, AssetStatus.DEVELOPING),
    (AssetStatus.RESOLVED, AssetStatus.PLANTED),
    (AssetStatus.FULFILLED, AssetStatus.PLANTED),
})


def is_forbidden_transition(src: AssetStatus, dst: AssetStatus) -> bool:
    """检查 src→dst 是否在 FORBIDDEN_TRANSITIONS 中。

    Raises:
        TypeError: src 或 dst 不是 AssetStatus 实例。
    """
    if not isinstance(src, AssetStatus):
        raise TypeError(f"src must be AssetStatus, got {type(src).__name__}")
    if not isinstance(dst, AssetStatus):
        raise TypeError(f"dst must be AssetStatus, got {type(dst).__name__}")
    return (src, dst) in FORBIDDEN_TRANSITIONS
```

- [ ] **Step 4: 运行测试确认通过** — 期望 6 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/contracts.py tests/unit/domain/storyos/test_forbidden_transitions.py && git commit -m "feat(domain): add FORBIDDEN_TRANSITIONS + is_forbidden_transition helper"`

#### Task A5: RegistryAsset Protocol

**Files:**
- Modify: `domain/storyos/contracts.py`（追加）
- Create: `tests/unit/domain/storyos/test_registry_asset_protocol.py`

- [ ] **Step 1: 写失败测试**

```python
from domain.storyos.contracts import RegistryAsset, AssetStatus


def test_empty_class_does_not_satisfy_protocol():
    class Empty:
        pass
    assert not isinstance(Empty(), RegistryAsset)


def test_partial_class_does_not_satisfy_protocol():
    class Partial:
        id = "x"
        status = AssetStatus.ACTIVE
        # missing linked_assets
    assert not isinstance(Partial(), RegistryAsset)


def test_full_class_satisfies_protocol():
    class Full:
        id = "x"
        status = AssetStatus.ACTIVE
        linked_assets: dict = {}
    assert isinstance(Full(), RegistryAsset)
```

- [ ] **Step 2: 运行测试确认失败** — `pytest tests/unit/domain/storyos/test_registry_asset_protocol.py -v` 期望 `ImportError`
- [ ] **Step 3: 实现** — 在 `domain/storyos/contracts.py` 追加：

```python
from typing import Protocol, runtime_checkable


@runtime_checkable
class RegistryAsset(Protocol):
    """所有 narrative asset 实体的 duck-typing 协议。

    任何实现需提供 id / status / linked_assets 三个属性。
    """

    id: str
    status: AssetStatus
    linked_assets: dict[str, str]
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/contracts.py tests/unit/domain/storyos/test_registry_asset_protocol.py && git commit -m "feat(domain): add RegistryAsset runtime-checkable protocol"`

---

### Group B: Value Objects（5 任务）

#### Task B1: SFLogRecord + SFLogParam（sub-spec §1 锁定 6 字段）

**Files:**
- Create: `domain/storyos/value_objects/__init__.py`（空文件）
- Create: `domain/storyos/value_objects/sf_log.py`
- Create: `tests/unit/domain/storyos/value_objects/__init__.py`（空文件）
- Create: `tests/unit/domain/storyos/value_objects/test_sf_log.py`

- [ ] **Step 1: 写失败测试** — `tests/unit/domain/storyos/value_objects/test_sf_log.py`

```python
import pytest
from pydantic import ValidationError
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogParam, SFLogRecord


def test_sf_log_param_constructs():
    p = SFLogParam(key="char_id", value="alice")
    assert p.key == "char_id"
    assert p.value == "alice"


def test_sf_log_param_forbids_extra():
    with pytest.raises(ValidationError):
        SFLogParam(key="k", value="v", extra="x")


def test_sf_log_param_is_frozen():
    p = SFLogParam(key="k", value="v")
    with pytest.raises(ValidationError):
        p.key = "kk"  # type: ignore[misc]


def test_sf_log_record_minimum_required():
    rec = SFLogRecord(
        log_type=SFLogType.MYSTERY_CLUE,
        params={"mystery_id": "m1", "content": "blood"},
        raw="<!-- SF_LOG MYSTERY_CLUE mystery_id=\"m1\" content=\"blood\" -->",
        chapter_id=3,
        char_position=120,
    )
    assert rec.log_type == SFLogType.MYSTERY_CLUE
    assert rec.params == {"mystery_id": "m1", "content": "blood"}
    assert rec.chapter_id == 3
    assert rec.char_position == 120
    assert rec.asset_id is None


def test_sf_log_record_with_asset_id():
    rec = SFLogRecord(
        log_type=SFLogType.MYSTERY_CLUE,
        params={"mystery_id": "m1"},
        raw="<!-- SF_LOG ... -->",
        chapter_id=1,
        char_position=0,
        asset_id="m1",
    )
    assert rec.asset_id == "m1"


def test_sf_log_record_forbids_extra():
    with pytest.raises(ValidationError):
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={"k": "v"},
            raw="<!-- ... -->",
            chapter_id=1,
            char_position=0,
            extra="nope",
        )


def test_sf_log_record_get_param_returns_value():
    rec = SFLogRecord(
        log_type=SFLogType.MYSTERY_CLUE,
        params={"mystery_id": "m1", "content": "x"},
        raw="<!-- ... -->",
        chapter_id=1,
        char_position=0,
    )
    assert rec.get_param("mystery_id") == "m1"
    assert rec.get_param("missing") is None
    assert rec.get_param("missing", default="d") == "d"


def test_sf_log_record_get_required_param_raises():
    rec = SFLogRecord(
        log_type=SFLogType.MYSTERY_CLUE,
        params={"k": "v"},
        raw="<!-- ... -->",
        chapter_id=1,
        char_position=0,
    )
    with pytest.raises(ValueError, match="requires param 'mystery_id'"):
        rec.get_required_param("mystery_id")


def test_sf_log_record_chapter_id_must_be_positive():
    with pytest.raises(ValidationError):
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={"k": "v"},
            raw="<!-- ... -->",
            chapter_id=0,
            char_position=0,
        )


def test_sf_log_record_char_position_must_be_non_negative():
    with pytest.raises(ValidationError):
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={"k": "v"},
            raw="<!-- ... -->",
            chapter_id=1,
            char_position=-1,
        )


def test_sf_log_record_params_must_be_non_empty():
    with pytest.raises(ValidationError):
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={},
            raw="<!-- ... -->",
            chapter_id=1,
            char_position=0,
        )
```

- [ ] **Step 2: 运行测试确认失败** — `pytest tests/unit/domain/storyos/value_objects/test_sf_log.py -v` 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `domain/storyos/value_objects/sf_log.py`：

```python
"""SFLogRecord + SFLogParam（sub-spec §1 锁定）。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SFLogParam(BaseModel):
    """SF_LOG 单个参数（key=value 解析结果）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    value: str


class SFLogRecord(BaseModel):
    """从章节文本中提取的单条 SF_LOG 记录。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    log_type: "SFLogType"  # forward ref；实际从 contracts 导入
    params: dict[str, str] = Field(min_length=1)
    raw: str = Field(min_length=1)
    chapter_id: int = Field(ge=1)
    char_position: int = Field(ge=0)
    asset_id: str | None = None

    def get_param(self, key: str, default: str | None = None) -> str | None:
        return self.params.get(key, default)

    def get_required_param(self, key: str) -> str:
        if key not in self.params:
            from domain.storyos.contracts import SFLogType as _T
            log_type_val = self.log_type.value if isinstance(self.log_type, _T) else str(self.log_type)
            raise ValueError(
                f"SFLogRecord requires param '{key}' for log_type {log_type_val}"
            )
        return self.params[key]
```

并在 `domain/storyos/value_objects/sf_log.py` 文件顶部添加 import 解决 forward ref：

```python
from __future__ import annotations

from typing import TYPE_CHECKING
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from domain.storyos.contracts import SFLogType
```

（注意保留 Pydantic v2 的 forward ref 兼容 — 上面已用 `from __future__ import annotations`）

- [ ] **Step 4: 运行测试确认通过** — 期望 11 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/value_objects/ tests/unit/domain/storyos/value_objects/ && git commit -m "feat(domain): add SFLogRecord + SFLogParam value objects (sub-spec §1)"`

#### Task B2: CascadeStep

**Files:**
- Create: `domain/storyos/value_objects/cascade.py`
- Create: `tests/unit/domain/storyos/value_objects/test_cascade_step.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from pydantic import ValidationError
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep


def test_cascade_step_minimum_required():
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery",
        source_asset_id="m1",
        target_asset_type="expectation",
        target_asset_id="e1",
        new_status=AssetStatus.ACTIVE,
        reason="climax",
    )
    assert step.trigger == CascadeTrigger.MYSTERY_REVEALED
    assert step.reason == "climax"
    assert step.intensity_delta is None


def test_cascade_step_with_intensity_delta():
    step = CascadeStep(
        trigger=CascadeTrigger.CONFLICT_ESCALATED,
        source_asset_type="conflict",
        source_asset_id="c1",
        target_asset_type="expectation",
        target_asset_id="e1",
        intensity_delta=30,
        reason="escalated to CRITICAL",
    )
    assert step.intensity_delta == 30
    assert step.new_status is None


def test_cascade_step_requires_status_or_intensity():
    with pytest.raises(ValidationError, match="new_status or intensity_delta"):
        CascadeStep(
            trigger=CascadeTrigger.MYSTERY_REVEALED,
            source_asset_type="mystery",
            source_asset_id="m1",
            target_asset_type="expectation",
            target_asset_id="e1",
            reason="bad",
        )


def test_cascade_step_default_reason_is_empty():
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery",
        source_asset_id="m1",
        target_asset_type="expectation",
        target_asset_id="e1",
        new_status=AssetStatus.ACTIVE,
    )
    assert step.reason == ""


def test_cascade_step_is_frozen():
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery",
        source_asset_id="m1",
        target_asset_type="expectation",
        target_asset_id="e1",
        new_status=AssetStatus.ACTIVE,
    )
    with pytest.raises(ValidationError):
        step.reason = "x"  # type: ignore[misc]
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `domain/storyos/value_objects/cascade.py`：

```python
"""CascadeStep + CascadeRules + CascadeResult（spec §3.2）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from domain.storyos.contracts import AssetStatus, CascadeTrigger


class CascadeStep(BaseModel):
    """单步级联动作。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    trigger: "CascadeTrigger"
    source_asset_type: str = Field(min_length=1)
    source_asset_id: str = Field(min_length=1)
    target_asset_type: str = Field(min_length=1)
    target_asset_id: str = Field(min_length=1)
    new_status: "AssetStatus | None" = None
    intensity_delta: int | None = None
    reason: str = ""

    @model_validator(mode="after")
    def _check_status_or_intensity(self) -> "CascadeStep":
        if self.new_status is None and self.intensity_delta is None:
            raise ValueError(
                "CascadeStep requires either new_status or intensity_delta"
            )
        return self
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/value_objects/cascade.py tests/unit/domain/storyos/value_objects/test_cascade_step.py && git commit -m "feat(domain): add CascadeStep with status/intensity validator"`

#### Task B3: CascadeResult + CascadeRules（带 cycle detection）

**Files:**
- Modify: `domain/storyos/value_objects/cascade.py`（追加）
- Create: `tests/unit/domain/storyos/value_objects/test_cascade_rules.py`

- [ ] **Step 1: 写失败测试**

```python
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep, CascadeResult, CascadeRules


def _step(src_type: str, src_id: str, dst_type: str, dst_id: str):
    return CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type=src_type,
        source_asset_id=src_id,
        target_asset_type=dst_type,
        target_asset_id=dst_id,
        new_status=AssetStatus.ACTIVE,
    )


def test_cascade_result_empty():
    r = CascadeResult()
    assert r.steps_executed == []
    assert r.blocked_steps == []
    assert r.max_depth_reached == 0


def test_cascade_rules_apply_to_no_cycle():
    rules = CascadeRules()
    s1 = _step("mystery", "m1", "expectation", "e1")
    s2 = _step("expectation", "e1", "promise", "p1")
    visited: set[str] = set()
    r1 = rules.apply_to(s1, visited, max_depth=3)
    assert r1["would_create_cycle"] is False
    assert "m1" in visited
    r2 = rules.apply_to(s2, visited, max_depth=3)
    assert r2["would_create_cycle"] is False
    assert "e1" in visited


def test_cascade_rules_detects_cycle():
    rules = CascadeRules()
    visited: set[str] = {"e1", "p1", "m1"}
    s = _step("promise", "p1", "expectation", "e1")
    r = rules.apply_to(s, visited, max_depth=3)
    assert r["would_create_cycle"] is True


def test_cascade_rules_max_depth():
    rules = CascadeRules()
    visited: set[str] = set()
    s = _step("mystery", "m1", "expectation", "e1")
    r = rules.apply_to(s, visited, max_depth=0)
    assert r["depth_exceeded"] is True
    assert r["would_create_cycle"] is False
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ImportError`
- [ ] **Step 3: 实现** — 在 `domain/storyos/value_objects/cascade.py` 追加：

```python
class CascadeResult(BaseModel):
    """单次级联执行结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    steps_executed: list["CascadeStep"] = Field(default_factory=list)
    blocked_steps: list["CascadeStep"] = Field(default_factory=list)
    max_depth_reached: int = 0


class CascadeRules:
    """级联规则工具（cycle detection + depth check）。"""

    def apply_to(
        self,
        step: "CascadeStep",
        visited: set[str],
        max_depth: int,
    ) -> dict:
        """判定一个 CascadeStep 是否可执行。

        Returns:
            dict with keys:
                - would_create_cycle: bool
                - depth_exceeded: bool
                - reason: str | None
        """
        if step.target_asset_id in visited:
            return {
                "would_create_cycle": True,
                "depth_exceeded": False,
                "reason": f"target {step.target_asset_id} already visited",
            }
        depth = len(visited)
        if depth >= max_depth:
            return {
                "would_create_cycle": False,
                "depth_exceeded": True,
                "reason": f"depth {depth} >= max_depth {max_depth}",
            }
        return {
            "would_create_cycle": False,
            "depth_exceeded": False,
            "reason": None,
        }
```

并在文件顶部 import 区域加：

```python
from pydantic import ConfigDict, Field, model_validator  # noqa: F401
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/value_objects/cascade.py tests/unit/domain/storyos/value_objects/test_cascade_rules.py && git commit -m "feat(domain): add CascadeResult + CascadeRules with cycle/depth detection"`

#### Task B4: PredeclaredChange + PredeclaredChanges（XOR 校验）

**Files:**
- Create: `domain/storyos/value_objects/predeclared.py`
- Create: `tests/unit/domain/storyos/value_objects/test_predeclared_change.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from pydantic import ValidationError
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.predeclared import (
    PredeclaredChange, PredeclaredChanges,
)


def test_predeclared_change_with_asset_id():
    p = PredeclaredChange(
        log_type=SFLogType.MYSTERY_CLUE,
        asset_type="mystery",
        asset_id="m1",
        expected_params={"content": "blood"},
    )
    assert p.asset_id == "m1"
    assert p.asset_pair is None


def test_predeclared_change_with_asset_pair():
    p = PredeclaredChange(
        log_type=SFLogType.CHARACTER_RELATION_CHANGE,
        asset_type="character",
        asset_pair=("alice", "bob"),
    )
    assert p.asset_pair == ("alice", "bob")
    assert p.asset_id is None


def test_predeclared_change_rejects_both_set():
    with pytest.raises(ValidationError, match="exactly one"):
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery",
            asset_id="m1",
            asset_pair=("x", "y"),
        )


def test_predeclared_change_rejects_neither_set():
    with pytest.raises(ValidationError, match="exactly one"):
        PredeclaredChange(
            log_type=SFLogType.MYSTERY_CLUE,
            asset_type="mystery",
        )


def test_predeclared_changes_aggregate():
    p1 = PredeclaredChange(
        log_type=SFLogType.MYSTERY_CLUE, asset_type="mystery", asset_id="m1",
    )
    p2 = PredeclaredChange(
        log_type=SFLogType.CHARACTER_RELATION_CHANGE,
        asset_type="character", asset_pair=("a", "b"),
    )
    pc = PredeclaredChanges(items=[p1, p2])
    assert len(list(pc)) == 2
    assert p1 in pc
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ImportError`
- [ ] **Step 3: 实现** — `domain/storyos/value_objects/predeclared.py`：

```python
"""PredeclaredChange + PredeclaredChanges（spec §3.2 / §4.4）。"""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:
    from domain.storyos.contracts import SFLogType


class PredeclaredChange(BaseModel):
    """LLM 在生成章节前预声明的 state 变更。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    log_type: "SFLogType"
    asset_type: str = Field(min_length=1)
    asset_id: str | None = None
    asset_pair: tuple[str, str] | None = None
    expected_params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _xor_id_pair(self) -> "PredeclaredChange":
        id_set = self.asset_id is not None
        pair_set = self.asset_pair is not None
        if id_set == pair_set:
            raise ValueError(
                f"PredeclaredChange requires exactly one of asset_id or asset_pair, "
                f"got asset_id={self.asset_id}, asset_pair={self.asset_pair}"
            )
        return self


class PredeclaredChanges(BaseModel):
    """PredeclaredChange 的聚合容器。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list["PredeclaredChange"] = Field(default_factory=list)

    def __iter__(self):
        return iter(self.items)

    def __contains__(self, item: "PredeclaredChange") -> bool:
        return item in self.items

    def __len__(self) -> int:
        return len(self.items)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/value_objects/predeclared.py tests/unit/domain/storyos/value_objects/test_predeclared_change.py && git commit -m "feat(domain): add PredeclaredChange with XOR validator + aggregate container"`

#### Task B5: MatchReport + FormatError

**Files:**
- Create: `domain/storyos/value_objects/match_report.py`
- Create: `domain/storyos/value_objects/format_error.py`
- Create: `tests/unit/domain/storyos/value_objects/test_match_report.py`
- Create: `tests/unit/domain/storyos/value_objects/test_format_error.py`

- [ ] **Step 1: 写失败测试** — `tests/unit/domain/storyos/value_objects/test_match_report.py`

```python
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.predeclared import PredeclaredChange
from domain.storyos.value_objects.sf_log import SFLogRecord
from domain.storyos.value_objects.match_report import MatchReport


def _change(asset_id="m1", log_type=SFLogType.MYSTERY_CLUE):
    return PredeclaredChange(log_type=log_type, asset_type="mystery", asset_id=asset_id)


def _record(asset_id="m1", log_type=SFLogType.MYSTERY_CLUE):
    return SFLogRecord(
        log_type=log_type,
        params={"k": "v"},
        raw="<!-- ... -->",
        chapter_id=1,
        char_position=0,
        asset_id=asset_id,
    )


def test_match_report_empty_no_retry_no_warnings():
    r = MatchReport()
    assert r.should_retry is False
    assert r.has_warnings is False
    assert r.predeclared_total == 0
    assert r.predeclared_implemented == 0
    assert r.match_rate == 1.0  # 0/0 定义为 1.0（fully matched）


def test_match_report_partial_match_calculates_rate():
    """spec §4.4 锁定：match_rate = predeclared_implemented / predeclared_total。"""
    r = MatchReport(
        predeclared_total=4, predeclared_implemented=3,
        missing_changes=[_change()], unexpected_records=[],
    )
    assert r.match_rate == 0.75
    assert r.should_retry is True


def test_match_report_retry_when_missing():
    r = MatchReport(missing_changes=[_change()])
    assert r.should_retry is True
    assert r.has_warnings is False


def test_match_report_warning_when_unexpected():
    r = MatchReport(unexpected_records=[_record()])
    assert r.has_warnings is True
    assert r.should_retry is False


def test_match_report_both_can_be_true():
    r = MatchReport(
        missing_changes=[_change()],
        unexpected_records=[_record()],
    )
    assert r.should_retry is True
    assert r.has_warnings is True
```

`tests/unit/domain/storyos/value_objects/test_format_error.py`：

```python
from domain.storyos.value_objects.format_error import FormatError


def test_format_error_constructs():
    e = FormatError(
        code="MALFORMED_TAG",
        message="missing closing -->",
        raw_text="<!-- SF_LOG MYSTERY",
        char_position=42,
    )
    assert e.code == "MALFORMED_TAG"
    assert e.message == "missing closing -->"
    assert e.raw_text == "<!-- SF_LOG MYSTERY"
    assert e.char_position == 42
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`（match_report 模块不存在）
- [ ] **Step 3: 实现** — 创建 `domain/storyos/value_objects/match_report.py`：

```python
"""MatchReport（spec §4.4 锁定两级重试）。

spec §4.4 锁定字段：
  - predeclared_total: int
  - predeclared_implemented: int
  - missing_changes: list[PredeclaredChange]
  - unexpected_records: list[SFLogRecord]
  - match_rate: float
  - properties: should_retry / has_warnings
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, computed_field

if TYPE_CHECKING:
    from domain.storyos.value_objects.predeclared import PredeclaredChange
    from domain.storyos.value_objects.sf_log import SFLogRecord


class MatchReport(BaseModel):
    """预声明 vs 实际 SF_LOG 的匹配报告（spec §4.4 锁定）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    predeclared_total: int = 0
    predeclared_implemented: int = 0
    missing_changes: list["PredeclaredChange"] = Field(default_factory=list)
    unexpected_records: list["SFLogRecord"] = Field(default_factory=list)

    @computed_field
    @property
    def match_rate(self) -> float:
        """spec §4.4 锁定：predeclared_implemented / predeclared_total。"""
        if self.predeclared_total == 0:
            return 1.0  # 无 predeclared 定义为完全匹配
        return self.predeclared_implemented / self.predeclared_total

    @property
    def should_retry(self) -> bool:
        return len(self.missing_changes) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.unexpected_records) > 0
```

创建 `domain/storyos/value_objects/format_error.py`：

```python
"""FormatError — SF_LOG 解析错误的轻量数据类。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatError:
    """SF_LOG 格式错误的不可变记录。"""

    code: str
    message: str
    raw_text: str
    char_position: int
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 + 1 = 5 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/value_objects/ tests/unit/domain/storyos/value_objects/ && git commit -m "feat(domain): add MatchReport properties + FormatError dataclass"`

---

### Group C: 8 Entity Types（8 任务）

> **通用约定**：所有实体为 `@dataclass(frozen=True)`，含 `id: str`、`status: AssetStatus`、`created_chapter: int`；实体不可变，状态变更返回新对象。

#### Task C1: Conflict + ConflictIntensity

**Files:**
- Create: `domain/storyos/entities/__init__.py`（空文件）
- Create: `domain/storyos/entities/conflict.py`
- Create: `tests/unit/domain/storyos/entities/__init__.py`（空文件）
- Create: `tests/unit/domain/storyos/entities/test_conflict.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity


def test_conflict_intensity_has_4_levels():
    assert {m.name for m in ConflictIntensity} == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert ConflictIntensity.LOW.value == 1
    assert ConflictIntensity.CRITICAL.value == 4


def test_conflict_minimum_required():
    c = Conflict(
        id="c1",
        novel_id="n1",
        description="alice vs bob",
        intensity=ConflictIntensity.MEDIUM,
        status=AssetStatus.ACTIVE,
        involved_characters=("alice", "bob"),
        created_chapter=1,
    )
    assert c.id == "c1"
    assert c.intensity == ConflictIntensity.MEDIUM
    assert c.linked_conflicts == ()


def test_conflict_escalate_low_to_medium():
    c = Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
        involved_characters=("a",), created_chapter=1,
    )
    c2 = c.escalate()
    assert c2.intensity == ConflictIntensity.MEDIUM
    assert c2.id == c.id
    assert c2 is not c  # new object


def test_conflict_escalate_critical_raises():
    c = Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.CRITICAL, status=AssetStatus.ACTIVE,
        involved_characters=("a",), created_chapter=1,
    )
    with pytest.raises(ValueError, match="already CRITICAL"):
        c.escalate()


def test_conflict_forbids_extra():
    with pytest.raises(TypeError):
        Conflict(
            id="c1", novel_id="n1", description="x",
            intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
            involved_characters=("a",), created_chapter=1,
            extra_field="nope",  # type: ignore[call-arg]
        )
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `domain/storyos/entities/conflict.py`：

```python
"""Conflict 实体（spec §3.1 列出，§4.2 cascade 规则之一）。"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import IntEnum


from domain.storyos.contracts import AssetStatus


class ConflictIntensity(IntEnum):
    """冲突强度（数值越大越剧烈，cascade +30 一档）。"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass(frozen=True)
class Conflict:
    """冲突实体：角色/阵营/事件 之间的张力。"""

    id: str
    novel_id: str
    description: str
    intensity: ConflictIntensity
    status: AssetStatus
    involved_characters: tuple[str, ...]
    created_chapter: int
    linked_conflicts: tuple[str, ...] = ()

    def __post_init__(self):
        if self.created_chapter < 1:
            raise ValueError("created_chapter must be >= 1")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.novel_id or not self.novel_id.strip():
            raise ValueError("novel_id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if not self.involved_characters:
            raise ValueError("involved_characters must not be empty")

    def escalate(self) -> "Conflict":
        """提升一档 intensity（LOW→MEDIUM→HIGH→CRITICAL）。"""
        levels = list(ConflictIntensity)
        idx = levels.index(self.intensity)
        if idx == len(levels) - 1:
            raise ValueError(
                f"Conflict {self.id} is already CRITICAL; cannot escalate"
            )
        return replace(self, intensity=levels[idx + 1])
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/entities/conflict.py tests/unit/domain/storyos/entities/test_conflict.py && git commit -m "feat(domain): add Conflict entity with escalate() transition"`

#### Task C2: Mystery + Clue（sub-spec §3 锁定 9 字段 + ClueCategory）

**Files:**
- Create: `domain/storyos/entities/mystery.py`
- Create: `tests/unit/domain/storyos/entities/test_mystery.py`

- [ ] **Step 1: 写失败测试** — `tests/unit/domain/storyos/entities/test_mystery.py`

```python
import pytest
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.mystery import Clue, ClueCategory, Mystery


def test_clue_category_has_5_values():
    assert {m.name for m in ClueCategory} == {
        "TRUTH", "RELATIONSHIP", "IDENTITY", "ABILITY", "OTHER",
    }


def test_clue_minimum_required():
    c = Clue(
        id="cl1",
        mystery_id="m1",
        description="blood on the knife",
        source_chapter=2,
        source_location="kitchen",
    )
    assert c.status == AssetStatus.PLANTED
    assert c.category == ClueCategory.TRUTH
    assert c.discovered_in_chapter is None
    assert c.invalidated_in_chapter is None


def test_clue_discover_returns_new():
    c = Clue(
        id="cl1", mystery_id="m1", description="x",
        source_chapter=2, source_location="loc",
    )
    c2 = c.discover(chapter=5)
    assert c2 is not c
    assert c2.status == AssetStatus.REVEALED
    assert c2.discovered_in_chapter == 5


def test_clue_discover_must_be_after_source():
    c = Clue(
        id="cl1", mystery_id="m1", description="x",
        source_chapter=5, source_location="loc",
    )
    with pytest.raises(ValueError, match="< source_chapter"):
        c.discover(chapter=2)


def test_clue_invalidate_from_planted():
    c = Clue(
        id="cl1", mystery_id="m1", description="x",
        source_chapter=2, source_location="loc",
    )
    c2 = c.invalidate(chapter=8)
    assert c2.status == AssetStatus.DEAD
    assert c2.invalidated_in_chapter == 8


def test_clue_invalidate_from_revealed():
    c = Clue(
        id="cl1", mystery_id="m1", description="x",
        source_chapter=2, source_location="loc",
        status=AssetStatus.REVEALED, discovered_in_chapter=5,
    )
    c2 = c.invalidate(chapter=8)
    assert c2.status == AssetStatus.DEAD


def test_clue_invalidate_from_dead_raises():
    c = Clue(
        id="cl1", mystery_id="m1", description="x",
        source_chapter=2, source_location="loc",
        status=AssetStatus.DEAD, invalidated_in_chapter=8,
    )
    with pytest.raises(ValueError, match="Cannot invalidate clue in status"):
        c.invalidate(chapter=9)


def test_mystery_with_clues():
    cl1 = Clue(id="cl1", mystery_id="m1", description="a", source_chapter=1, source_location="x")
    cl2 = Clue(id="cl2", mystery_id="m1", description="b", source_chapter=2, source_location="y")
    m = Mystery(
        id="m1", novel_id="n1", description="who killed X",
        status=AssetStatus.PLANTED, created_chapter=1, clues=(cl1, cl2),
    )
    assert len(m.clues) == 2


def test_mystery_add_clue_returns_new():
    m = Mystery(
        id="m1", novel_id="n1", description="x",
        status=AssetStatus.PLANTED, created_chapter=1,
    )
    cl = Clue(id="cl1", mystery_id="m1", description="a", source_chapter=1, source_location="x")
    m2 = m.add_clue(cl)
    assert len(m2.clues) == 1
    assert m2.clues[0] is cl
    assert len(m.clues) == 0  # original unchanged


def test_mystery_related_mystery_field():
    m = Mystery(
        id="m1", novel_id="n1", description="x",
        status=AssetStatus.PLANTED, created_chapter=1,
        related_mystery="m0",
    )
    assert m.related_mystery == "m0"
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `domain/storyos/entities/mystery.py`（sub-spec §3 锁定）：

```python
"""Mystery + Clue 实体（sub-spec §3 锁定字段）。"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from domain.storyos.contracts import AssetStatus


class ClueCategory(str, Enum):
    """Clue 语义分类（与 RevealedClueItem.category 对齐）。"""

    TRUTH = "truth"
    RELATIONSHIP = "relationship"
    IDENTITY = "identity"
    ABILITY = "ability"
    OTHER = "other"


@dataclass(frozen=True)
class Clue:
    """Mystery 的组成成分。"""

    id: str
    mystery_id: str
    description: str
    source_chapter: int
    source_location: str
    category: ClueCategory = ClueCategory.TRUTH
    status: AssetStatus = AssetStatus.PLANTED
    discovered_in_chapter: int | None = None
    invalidated_in_chapter: int | None = None

    def __post_init__(self):
        if self.source_chapter < 1:
            raise ValueError("source_chapter must be >= 1")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if not self.source_location or not self.source_location.strip():
            raise ValueError("source_location cannot be empty")
        if self.discovered_in_chapter is not None and self.discovered_in_chapter < self.source_chapter:
            raise ValueError("discovered_in_chapter must be >= source_chapter")
        if self.invalidated_in_chapter is not None and self.invalidated_in_chapter < self.source_chapter:
            raise ValueError("invalidated_in_chapter must be >= source_chapter")
        if self.status == AssetStatus.REVEALED and self.discovered_in_chapter is None:
            raise ValueError("REVEALED status requires discovered_in_chapter")
        if self.status == AssetStatus.DEAD and self.invalidated_in_chapter is None:
            raise ValueError("DEAD status requires invalidated_in_chapter")

    def discover(self, chapter: int) -> "Clue":
        if self.status != AssetStatus.PLANTED:
            raise ValueError(f"Cannot discover clue in status {self.status.value}")
        if chapter < self.source_chapter:
            raise ValueError(
                f"discover chapter {chapter} < source_chapter {self.source_chapter}"
            )
        return replace(
            self, status=AssetStatus.REVEALED, discovered_in_chapter=chapter,
        )

    def invalidate(self, chapter: int) -> "Clue":
        if self.status not in (AssetStatus.PLANTED, AssetStatus.REVEALED):
            raise ValueError(f"Cannot invalidate clue in status {self.status.value}")
        return replace(
            self, status=AssetStatus.DEAD, invalidated_in_chapter=chapter,
        )


@dataclass(frozen=True)
class Mystery:
    """悬疑/谜团实体（包含多条 Clue）。"""

    id: str
    novel_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    clues: tuple[Clue, ...] = ()
    related_mystery: str | None = None

    def __post_init__(self):
        if self.created_chapter < 1:
            raise ValueError("created_chapter must be >= 1")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")

    def add_clue(self, clue: Clue) -> "Mystery":
        if clue.mystery_id != self.id:
            raise ValueError(
                f"clue.mystery_id={clue.mystery_id} != mystery.id={self.id}"
            )
        return replace(self, clues=self.clues + (clue,))
```

> **DDD 修正**：1A **不**实现 `Clue.to_revealed_clue_item()` 方法（domain 不应依赖 application 层）。该投影由 1B `MysteryService` 完成，详见 [`2026-07-02-storyos-asset-field-spec.md`](../specs/2026-07-02-storyos-asset-field-spec.md) §3.6 修正说明。

- [ ] **Step 4: 运行测试确认通过** — 期望 10 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/entities/mystery.py tests/unit/domain/storyos/entities/test_mystery.py && git commit -m "feat(domain): add Mystery + Clue entities (sub-spec §3, 9 fields + ClueCategory)"`

#### Task C3: Twist + TwistType（sub-spec §2 锁定 6 值）

**Files:**
- Create: `domain/storyos/entities/twist.py`
- Create: `tests/unit/domain/storyos/entities/test_twist.py`

- [ ] **Step 1: 写失败测试**

```python
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.twist import Twist, TwistType


def test_twist_type_has_6_values():
    assert len(TwistType) == 6
    expected = {
        "IDENTITY_REVEAL", "BETRAYAL", "FORTUNE_REVERSAL",
        "WORLD_RULE_REVEAL", "SACRIFICE", "TRUTH_REVEALED",
    }
    assert {m.name for m in TwistType} == expected


def test_twist_minimum_required():
    t = Twist(
        id="t1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=3,
        twist_type=TwistType.IDENTITY_REVEAL,
    )
    assert t.reveal_trigger is None
    assert t.forbidden_concurrent_twists == ()


def test_twist_with_reveal_trigger():
    t = Twist(
        id="t1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=3,
        twist_type=TwistType.TRUTH_REVEALED,
        reveal_trigger="mystery:m1:revealed",
    )
    assert t.reveal_trigger == "mystery:m1:revealed"


def test_twist_with_forbidden_concurrent():
    t = Twist(
        id="t1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=3,
        twist_type=TwistType.BETRAYAL,
        forbidden_concurrent_twists=("t2", "t3"),
    )
    assert t.forbidden_concurrent_twists == ("t2", "t3")
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `domain/storyos/entities/twist.py`：

```python
"""Twist 实体（sub-spec §2 锁定 6 类 TwistType）。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.storyos.contracts import AssetStatus


class TwistType(str, Enum):
    """Twist 的语义分类（sub-spec §2 锁定 6 类）。"""

    IDENTITY_REVEAL = "identity_reveal"            # 身份揭露（卧底/双面人/真身）
    BETRAYAL = "betrayal"                          # 背叛（盟友反目）
    FORTUNE_REVERSAL = "fortune_reversal"          # 命运反转
    WORLD_RULE_REVEAL = "world_rule_reveal"        # 世界规则揭示
    SACRIFICE = "sacrifice"                        # 牺牲
    TRUTH_REVEALED = "truth_revealed"              # 真相揭示


@dataclass(frozen=True)
class Twist:
    """叙事反转实体。"""

    id: str
    novel_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    twist_type: TwistType
    reveal_trigger: str | None = None
    forbidden_concurrent_twists: tuple[str, ...] = ()

    def __post_init__(self):
        if self.created_chapter < 1:
            raise ValueError("created_chapter must be >= 1")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/entities/twist.py tests/unit/domain/storyos/entities/test_twist.py && git commit -m "feat(domain): add Twist entity + TwistType (sub-spec §2, 6 values)"`

#### Task C4: Promise

**Files:**
- Create: `domain/storyos/entities/promise.py`
- Create: `tests/unit/domain/storyos/entities/test_promise.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.promise import Promise


def test_promise_minimum_required():
    p = Promise(
        id="p1", novel_id="n1", description="alice will return",
        made_in_chapter=1, status=AssetStatus.ACTIVE, importance=80,
    )
    assert p.fulfilled_in_chapter is None
    assert p.importance == 80


def test_promise_fulfill_returns_new():
    p = Promise(
        id="p1", novel_id="n1", description="x",
        made_in_chapter=1, status=AssetStatus.ACTIVE, importance=50,
    )
    p2 = p.fulfill(chapter=10)
    assert p2 is not p
    assert p2.status == AssetStatus.FULFILLED
    assert p2.fulfilled_in_chapter == 10


def test_promise_fulfill_already_fulfilled_raises():
    p = Promise(
        id="p1", novel_id="n1", description="x",
        made_in_chapter=1, status=AssetStatus.FULFILLED,
        fulfilled_in_chapter=5, importance=50,
    )
    with pytest.raises(ValueError, match="Cannot fulfill promise in status"):
        p.fulfill(chapter=10)


def test_promise_importance_out_of_range():
    with pytest.raises(ValueError, match="importance"):
        Promise(
            id="p1", novel_id="n1", description="x",
            made_in_chapter=1, status=AssetStatus.ACTIVE, importance=150,
        )
    with pytest.raises(ValueError, match="importance"):
        Promise(
            id="p1", novel_id="n1", description="x",
            made_in_chapter=1, status=AssetStatus.ACTIVE, importance=-1,
        )
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `domain/storyos/entities/promise.py`：

```python
"""Promise 实体（叙事承诺）。"""
from __future__ import annotations

from dataclasses import dataclass, replace

from domain.storyos.contracts import AssetStatus


@dataclass(frozen=True)
class Promise:
    """作者向读者做出的承诺（伏笔的语义对偶）。"""

    id: str
    novel_id: str
    description: str
    made_in_chapter: int
    status: AssetStatus
    importance: int
    fulfilled_in_chapter: int | None = None

    def __post_init__(self):
        if self.made_in_chapter < 1:
            raise ValueError("made_in_chapter must be >= 1")
        if not 0 <= self.importance <= 100:
            raise ValueError(f"importance must be in [0, 100], got {self.importance}")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if self.status == AssetStatus.FULFILLED and self.fulfilled_in_chapter is None:
            raise ValueError("FULFILLED status requires fulfilled_in_chapter")
        if (
            self.fulfilled_in_chapter is not None
            and self.fulfilled_in_chapter < self.made_in_chapter
        ):
            raise ValueError("fulfilled_in_chapter must be >= made_in_chapter")

    def fulfill(self, chapter: int) -> "Promise":
        if self.status != AssetStatus.ACTIVE:
            raise ValueError(f"Cannot fulfill promise in status {self.status.value}")
        if chapter < self.made_in_chapter:
            raise ValueError(
                f"fulfill chapter {chapter} < made_in_chapter {self.made_in_chapter}"
            )
        return replace(self, status=AssetStatus.FULFILLED, fulfilled_in_chapter=chapter)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/entities/promise.py tests/unit/domain/storyos/entities/test_promise.py && git commit -m "feat(domain): add Promise entity with fulfill() transition"`

#### Task C5: Reveal

**Files:**
- Create: `domain/storyos/entities/reveal.py`
- Create: `tests/unit/domain/storyos/entities/test_reveal.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.reveal import Reveal


def test_reveal_minimum_required():
    r = Reveal(
        id="rv1", novel_id="n1", content="x is the killer",
        status=AssetStatus.HIDDEN, related_mystery="m1",
    )
    assert r.revealed_in_chapter is None
    assert r.linked_to_conflict is None


def test_reveal_transition_hidden_to_revealed():
    r = Reveal(
        id="rv1", novel_id="n1", content="x",
        status=AssetStatus.HIDDEN, related_mystery="m1",
    )
    r2 = r.reveal(chapter=15)
    assert r2.status == AssetStatus.REVEALED
    assert r2.revealed_in_chapter == 15


def test_reveal_transition_already_revealed_raises():
    r = Reveal(
        id="rv1", novel_id="n1", content="x",
        status=AssetStatus.REVEALED, revealed_in_chapter=10,
        related_mystery="m1",
    )
    with pytest.raises(ValueError, match="Cannot reveal in status"):
        r.reveal(chapter=15)
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `domain/storyos/entities/reveal.py`：

```python
"""Reveal 实体（叙世揭示）。"""
from __future__ import annotations

from dataclasses import dataclass, replace

from domain.storyos.contracts import AssetStatus


@dataclass(frozen=True)
class Reveal:
    """叙事揭示（HIDDEN → REVEALED）。"""

    id: str
    novel_id: str
    content: str
    status: AssetStatus
    related_mystery: str | None
    linked_to_conflict: str | None = None
    revealed_in_chapter: int | None = None

    def __post_init__(self):
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be empty")
        if self.status == AssetStatus.REVEALED and self.revealed_in_chapter is None:
            raise ValueError("REVEALED status requires revealed_in_chapter")

    def reveal(self, chapter: int) -> "Reveal":
        if self.status != AssetStatus.HIDDEN:
            raise ValueError(f"Cannot reveal in status {self.status.value}")
        if chapter < 1:
            raise ValueError(f"chapter must be >= 1, got {chapter}")
        return replace(self, status=AssetStatus.REVEALED, revealed_in_chapter=chapter)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/entities/reveal.py tests/unit/domain/storyos/entities/test_reveal.py && git commit -m "feat(domain): add Reveal entity with reveal() transition"`

#### Task C6: Expectation（intensity clamp [0,100]）

**Files:**
- Create: `domain/storyos/entities/expectation.py`
- Create: `tests/unit/domain/storyos/entities/test_expectation.py`

- [ ] **Step 1: 写失败测试**

```python
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.expectation import Expectation


def test_expectation_minimum_required():
    e = Expectation(
        id="e1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1, intensity=50,
    )
    assert e.intensity == 50


def test_expectation_intensify_clamps_upper():
    e = Expectation(
        id="e1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1, intensity=95,
    )
    e2 = e.intensify(30)
    assert e2.intensity == 100  # clamped


def test_expectation_intensify_clamps_lower():
    e = Expectation(
        id="e1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1, intensity=10,
    )
    e2 = e.intensify(-50)
    assert e2.intensity == 0


def test_expectation_intensify_normal():
    e = Expectation(
        id="e1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1, intensity=50,
    )
    e2 = e.intensify(20)
    assert e2.intensity == 70


def test_expectation_initial_intensity_validated():
    import pytest
    with pytest.raises(ValueError):
        Expectation(
            id="e1", novel_id="n1", description="x",
            status=AssetStatus.ACTIVE, created_chapter=1, intensity=150,
        )
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `domain/storyos/entities/expectation.py`：

```python
"""Expectation 实体（读者预期，cascade 修改 intensity）。"""
from __future__ import annotations

from dataclasses import dataclass, replace

from domain.storyos.contracts import AssetStatus


@dataclass(frozen=True)
class Expectation:
    """读者对剧情的预期。"""

    id: str
    novel_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    intensity: int

    def __post_init__(self):
        if self.created_chapter < 1:
            raise ValueError("created_chapter must be >= 1")
        if not 0 <= self.intensity <= 100:
            raise ValueError(f"intensity must be in [0, 100], got {self.intensity}")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")

    def intensify(self, delta: int) -> "Expectation":
        """调整 intensity，自动 clamp 到 [0, 100]。"""
        new_intensity = max(0, min(100, self.intensity + delta))
        return replace(self, intensity=new_intensity)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/entities/expectation.py tests/unit/domain/storyos/entities/test_expectation.py && git commit -m "feat(domain): add Expectation entity with intensity clamp [0,100]"`

#### Task C7: Goal + ProgressMarker

**Files:**
- Create: `domain/storyos/entities/goal.py`
- Create: `tests/unit/domain/storyos/entities/test_goal.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.goal import Goal, ProgressMarker


def test_progress_marker_T0_to_T9():
    assert len(ProgressMarker) == 10
    assert ProgressMarker.T0.value == 0
    assert ProgressMarker.T9.value == 9


def test_goal_minimum_required():
    g = Goal(
        id="g1", novel_id="n1", description="defeat the demon lord",
        status=AssetStatus.ACTIVE, created_chapter=1,
        current_progress=ProgressMarker.T0,
    )
    assert g.current_progress == ProgressMarker.T0


def test_goal_advance_monotonic():
    g = Goal(
        id="g1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1,
        current_progress=ProgressMarker.T3,
    )
    g2 = g.advance(ProgressMarker.T5)
    assert g2.current_progress == ProgressMarker.T5


def test_goal_advance_rejects_backward():
    g = Goal(
        id="g1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1,
        current_progress=ProgressMarker.T5,
    )
    with pytest.raises(ValueError, match="must be >="):
        g.advance(ProgressMarker.T3)


def test_goal_advance_rejects_same_marker():
    g = Goal(
        id="g1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1,
        current_progress=ProgressMarker.T3,
    )
    with pytest.raises(ValueError, match="must be >="):
        g.advance(ProgressMarker.T3)
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `domain/storyos/entities/goal.py`：

```python
"""Goal 实体（角色/情节目标，ProgressMarker T0-T9）。"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum

from domain.storyos.contracts import AssetStatus


class ProgressMarker(IntEnum):
    """目标进度标记（T0=起点 → T9=达成）。"""

    T0 = 0
    T1 = 1
    T2 = 2
    T3 = 3
    T4 = 4
    T5 = 5
    T6 = 6
    T7 = 7
    T8 = 8
    T9 = 9


@dataclass(frozen=True)
class Goal:
    """叙事目标实体。"""

    id: str
    novel_id: str
    description: str
    status: AssetStatus
    created_chapter: int
    current_progress: ProgressMarker

    def __post_init__(self):
        if self.created_chapter < 1:
            raise ValueError("created_chapter must be >= 1")
        if not self.id or not self.id.strip():
            raise ValueError("id cannot be empty")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")

    def advance(self, marker: ProgressMarker) -> "Goal":
        if marker.value <= self.current_progress.value:
            raise ValueError(
                f"new marker {marker.name} must be >= current {self.current_progress.name}"
            )
        return replace(self, current_progress=marker)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/entities/goal.py tests/unit/domain/storyos/entities/test_goal.py && git commit -m "feat(domain): add Goal entity with ProgressMarker T0-T9 + monotonic advance()"`

#### Task C8: Foreshadowing（旧表保留，1A 复制到新位置）

**Files:**
- Create: `domain/storyos/entities/foreshadowing.py`（**新位置**，不删旧）
- Create: `tests/unit/domain/storyos/entities/test_foreshadowing.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from domain.storyos.contracts import AssetStatus
from domain.novel.value_objects.foreshadowing import ImportanceLevel
from domain.storyos.entities.foreshadowing import Foreshadowing


def test_foreshadowing_minimum_required():
    f = Foreshadowing(
        id="fs1", novel_id="n1", description="the scar on his hand",
        importance=ImportanceLevel.HIGH, status=AssetStatus.PLANTED,
        planted_in_chapter=2,
    )
    assert f.suggested_resolve_chapter is None
    assert f.resolved_in_chapter is None
    assert f.novel_id == "n1"


def test_foreshadowing_status_uses_asset_status():
    f = Foreshadowing(
        id="fs1", novel_id="n1", description="x",
        importance=ImportanceLevel.MEDIUM, status=AssetStatus.PLANTED,
        planted_in_chapter=1,
    )
    # REVEALED 是 spec 附录 C 映射的 resolved 状态
    f2 = f.resolve(chapter=10)
    assert f2.status == AssetStatus.REVEALED
    assert f2.resolved_in_chapter == 10


def test_foreshadowing_abandon():
    f = Foreshadowing(
        id="fs1", novel_id="n1", description="x",
        importance=ImportanceLevel.LOW, status=AssetStatus.PLANTED,
        planted_in_chapter=1,
    )
    f2 = f.abandon(chapter=20)
    assert f2.status == AssetStatus.DEAD


def test_foreshadowing_resolve_already_resolved_raises():
    f = Foreshadowing(
        id="fs1", novel_id="n1", description="x",
        importance=ImportanceLevel.MEDIUM, status=AssetStatus.REVEALED,
        planted_in_chapter=1, resolved_in_chapter=5,
    )
    with pytest.raises(ValueError, match="Cannot resolve"):
        f.resolve(chapter=10)


def test_foreshadowing_importance_validation():
    with pytest.raises(ValueError, match="importance"):
        Foreshadowing(
            id="fs1", novel_id="n1", description="x",
            importance=999,  # type: ignore[arg-type]
            status=AssetStatus.PLANTED, planted_in_chapter=1,
        )
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `domain/storyos/entities/foreshadowing.py`：

```python
"""Foreshadowing 实体（新位置；旧位置 domain/novel/value_objects/foreshadowing.py 保留至 Phase 2）。

spec 附录 C 锁定旧→新状态映射：planted→PLANTED, resolved→REVEALED, abandoned→DEAD。
1A 不删除旧代码；1E 迁移脚本会引用本文件。
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from domain.novel.value_objects.foreshadowing import ImportanceLevel
from domain.storyos.contracts import AssetStatus


@dataclass(frozen=True)
class Foreshadowing:
    """伏笔实体（统一真相源，状态用 AssetStatus）。"""

    id: str
    novel_id: str
    description: str
    importance: ImportanceLevel
    status: AssetStatus
    planted_in_chapter: int
    suggested_resolve_chapter: int | None = None
    resolved_in_chapter: int | None = None

    def __post_init__(self):
        if self.planted_in_chapter < 1:
            raise ValueError("planted_in_chapter must be >= 1")
        if not self.description or not self.description.strip():
            raise ValueError("description cannot be empty")
        if self.status == AssetStatus.REVEALED and self.resolved_in_chapter is None:
            raise ValueError("REVEALED status requires resolved_in_chapter")
        if self.suggested_resolve_chapter is not None and self.suggested_resolve_chapter < 1:
            raise ValueError("suggested_resolve_chapter must be >= 1")
        if self.resolved_in_chapter is not None and self.resolved_in_chapter < 1:
            raise ValueError("resolved_in_chapter must be >= 1")
        if (
            self.resolved_in_chapter is not None
            and self.resolved_in_chapter < self.planted_in_chapter
        ):
            raise ValueError("resolved_in_chapter must be >= planted_in_chapter")
        if (
            self.suggested_resolve_chapter is not None
            and self.suggested_resolve_chapter < self.planted_in_chapter
        ):
            raise ValueError("suggested_resolve_chapter must be >= planted_in_chapter")

    def resolve(self, chapter: int) -> "Foreshadowing":
        if self.status != AssetStatus.PLANTED:
            raise ValueError(f"Cannot resolve foreshadowing in status {self.status.value}")
        if chapter < self.planted_in_chapter:
            raise ValueError(
                f"resolve chapter {chapter} < planted_in_chapter {self.planted_in_chapter}"
            )
        return replace(
            self, status=AssetStatus.REVEALED, resolved_in_chapter=chapter,
        )

    def abandon(self, chapter: int) -> "Foreshadowing":
        if self.status not in (AssetStatus.PLANTED, AssetStatus.REVEALED):
            raise ValueError(f"Cannot abandon foreshadowing in status {self.status.value}")
        return replace(self, status=AssetStatus.DEAD)
```

> **⚠️ 警告**：1A **不删除** `domain/novel/value_objects/foreshadowing.py`。旧代码由 Phase 2 决定；1E 迁移脚本引用新位置（`domain/storyos/entities/foreshadowing.py`）。

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed
- [ ] **Step 5: Commit** — `git add domain/storyos/entities/foreshadowing.py tests/unit/domain/storyos/entities/test_foreshadowing.py && git commit -m "feat(domain): add Foreshadowing entity to storyos (old location retained)"`

---

### Group D: Persistence 基础设施（5 任务）

#### Task D1: WriteTransaction public 类 + queue() 向后兼容

**Files:**
- Modify: `infrastructure/persistence/database/write_dispatch.py`（追加 WriteTransaction class）
- Create: `tests/unit/infrastructure/persistence/database/test_write_dispatch_transaction.py`

- [ ] **Step 1: 写失败测试**

```python
from infrastructure.persistence.database.write_dispatch import WriteTransaction


def test_write_transaction_constructs_empty():
    txn = WriteTransaction()
    assert txn is not None


def test_write_transaction_queue_adds_op():
    txn = WriteTransaction()
    called = []

    def op(conn):
        called.append(conn)

    txn.queue(op)
    assert len(txn._ops) == 1
    assert txn._ops[0] is op


def test_write_transaction_dispatches_to_writer():
    """通过 WriteDispatch 派发到 writer 线程（集成测试，1A 简化版）。"""
    from infrastructure.persistence.database.write_dispatch import WriteDispatch
    txn = WriteTransaction()
    received = []

    def op(_conn):
        received.append("ok")

    txn.queue(op)
    # 1A 阶段：WriteTransaction 仅作为数据载体；实际派发由 transaction() 负责（D2）
    assert txn._ops == [op]
```

- [ ] **Step 2: 运行测试确认失败** — `pytest tests/unit/infrastructure/persistence/database/test_write_dispatch_transaction.py -v` 期望 `ImportError`
- [ ] **Step 3: 实现** — 在 `infrastructure/persistence/database/write_dispatch.py` 追加（**文件末尾**）：

```python
class WriteTransaction:
    """单事务内多 op 容器（spec §3.5 锁定）。

    1A 阶段：仅作为数据载体，事务派发由 WriteDispatch.transaction()（D2）负责。
    1B 阶段：EvolutionBridgeService 会 queue_apply() 三个 op 提交到这里。
    """

    def __init__(self) -> None:
        self._ops: list = []

    def queue(self, op) -> None:
        """向后兼容的 op 入队（与 WriteDispatch.queue 同形）。"""
        self._ops.append(op)
```

并在 `infrastructure/persistence/database/__init__.py`（如不存在创建空文件）中 export。

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed
- [ ] **Step 5: Commit** — `git add infrastructure/persistence/database/write_dispatch.py tests/unit/infrastructure/persistence/database/test_write_dispatch_transaction.py && git commit -m "feat(write-dispatch): scaffold public WriteTransaction class (backward compat)"`

#### Task D2: WriteDispatch.transaction() 上下文管理器

**Files:**
- Modify: `infrastructure/persistence/database/write_dispatch.py`（追加 transaction 方法 + WriteTransaction 类扩展）
- Modify: `tests/unit/infrastructure/persistence/database/test_write_dispatch_transaction.py`

- [ ] **Step 1: 写失败测试**（追加到 test_write_dispatch_transaction.py）：

```python
from infrastructure.persistence.database.write_dispatch import WriteDispatch, WriteTransaction


def test_write_dispatch_has_transaction_method():
    assert hasattr(WriteDispatch, "transaction")


def test_transaction_context_returns_write_transaction():
    wd = WriteDispatch()
    with wd.transaction() as txn:
        assert isinstance(txn, WriteTransaction)


def test_transaction_normal_exit_commits_ops(monkeypatch):
    """正常退出 → 提交所有 _ops 到 enqueue_txn_batch。"""
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(ops) or True,
    )
    with wd.transaction() as txn:
        txn.queue(lambda c: None)
        txn.queue(lambda c: None)
    assert len(captured) == 1
    assert len(captured[0]) == 2


def test_transaction_exception_rolls_back(monkeypatch):
    """异常退出 → 丢弃 _ops，不调用 enqueue_txn_batch。"""
    wd = WriteDispatch()
    captured = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: captured.append(ops) or True,
    )
    with pytest.raises(RuntimeError):
        with wd.transaction() as txn:
            txn.queue(lambda c: None)
            raise RuntimeError("boom")
    assert captured == []  # no commit
```

并在文件顶部加 `import pytest`。

- [ ] **Step 2: 运行测试确认失败** — 期望 `AttributeError: 'WriteDispatch' object has no attribute 'transaction'`
- [ ] **Step 3: 实现** — 在 `infrastructure/persistence/database/write_dispatch.py` 追加 `WriteTransaction` 类与 `WriteDispatch.transaction()` 方法：

```python
import contextlib


# （在 WriteTransaction 类内追加）
class WriteTransaction:
    def __init__(self) -> None:
        self._ops: list = []

    def queue(self, op) -> None:
        self._ops.append(op)

    def run(self, executor) -> None:
        """由 WriteDispatch.transaction() 提交时调用。"""
        if not self._ops:
            return
        executor(self._ops)


# （在文件末尾追加 WriteDispatch 类）
class WriteDispatch:
    """统一写入派发（spec §3.5 锁定 transaction() 入口）。

    1A 阶段：transaction() 内部使用 enqueue_txn_batch 提交。
    1B 阶段：EvolutionBridgeService 会用此 API 包装三 op 单事务。
    """

    @contextlib.contextmanager
    def transaction(self):
        """单事务多 op 上下文管理器。

        Usage:
            with WriteDispatch().transaction() as txn:
                txn.queue(op1)
                txn.queue(op2)
        """
        txn = WriteTransaction()
        try:
            yield txn
        except BaseException:
            # 异常时丢弃 _ops（rollback 占位；D3 完善原子性）
            raise
        else:
            txn.run(enqueue_txn_batch)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed
- [ ] **Step 5: Commit** — `git add infrastructure/persistence/database/write_dispatch.py tests/unit/infrastructure/persistence/database/test_write_dispatch_transaction.py && git commit -m "feat(write-dispatch): add WriteDispatch.transaction() context manager"`

#### Task D3: queue_apply + 原子性 + 闭包陷阱修复

**Files:**
- Modify: `infrastructure/persistence/database/write_dispatch.py`（追加 queue_apply）
- Modify: `tests/unit/infrastructure/persistence/database/test_write_dispatch_transaction.py`

- [ ] **Step 1: 写失败测试**（追加到 test_write_dispatch_transaction.py）：

```python
import functools


def test_queue_apply_eager_binds_args():
    """queue_apply 的参数在调用时立即绑定（不延迟到 commit）。"""
    with WriteDispatch().transaction() as txn:
        counter = {"calls": 0}

        def fn(_conn, x, y):
            counter["calls"] += 1
            assert x + y == 3

        txn.queue_apply(fn, 1, 2)
        # 参数在入队时已绑定；执行应直接成功
        assert len(txn._ops) == 1
        # 模拟执行
        partial_op = txn._ops[0]
        partial_op(None)
        assert counter["calls"] == 1


def test_transaction_atomicity_on_exception(monkeypatch):
    """op 抛异常 → 后续 op 不执行（D3 阶段 rollback 完整实现）。"""
    wd = WriteDispatch()
    executed = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: [executed.append(op) for op in ops] or True,
    )
    with pytest.raises(RuntimeError):
        with wd.transaction() as txn:
            def op_a(_c): executed.append("a")
            def op_b(_c): raise RuntimeError("fail in b")
            def op_c(_c): executed.append("c")
            txn.queue(op_a)
            txn.queue(op_b)
            txn.queue(op_c)
    # enqueue_txn_batch 未被调用（异常时整体 rollback）
    assert executed == []


def test_transaction_order_preserved(monkeypatch):
    """op 按入队顺序执行。"""
    wd = WriteDispatch()
    executed = []
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: [executed.append(op) for op in ops] or True,
    )
    with wd.transaction() as txn:
        txn.queue(lambda c: executed.append("a"))
        txn.queue(lambda c: executed.append("b"))
        txn.queue(lambda c: executed.append("c"))
    assert executed == ["a", "b", "c"]
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `AttributeError: 'WriteTransaction' object has no attribute 'queue_apply'`
- [ ] **Step 3: 实现** — 在 `WriteTransaction` 类内追加：

```python
import functools  # 顶部 import


class WriteTransaction:
    def __init__(self) -> None:
        self._ops: list = []

    def queue(self, op) -> None:
        self._ops.append(op)

    def queue_apply(self, fn, *args, **kwargs) -> None:
        """入队 fn(conn, *args, **kwargs)。

        参数立即绑定（用 functools.partial）→ 闭包陷阱修复。
        1B 的 EvolutionBridgeService 用此 API 包装 evolution_apply_actions / registry_apply_with_cascade / sflog_event_record 三个 op。
        """
        self._ops.append(functools.partial(fn, *args, **kwargs))
```

并在 `WriteDispatch.transaction()` 的 `else` 分支前加 rollback 逻辑：

```python
    @contextlib.contextmanager
    def transaction(self):
        txn = WriteTransaction()
        try:
            yield txn
        except BaseException:
            # 异常时整体 rollback：不调用 enqueue_txn_batch
            raise
        else:
            txn.run(enqueue_txn_batch)
```

（保持与 D2 相同；D3 验证完整性）

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed
- [ ] **Step 5: Commit** — `git add infrastructure/persistence/database/write_dispatch.py tests/unit/infrastructure/persistence/database/test_write_dispatch_transaction.py && git commit -m "feat(write-dispatch): add queue_apply() with eager args + atomicity guarantee"`

> **⚠️ 关键测试**：`test_bridge_sql_transaction`（1B 阶段）必须用 mock evolution_apply 抛异常验证 3 表全 ROLLBACK。1A 范围仅覆盖 WriteDispatch 自身原子性。

#### Task D4: BaseRegistrySchema mixin（11 表共用字段）

**Files:**
- Create: `infrastructure/persistence/storyos/__init__.py`（空文件）
- Create: `infrastructure/persistence/storyos/schemas/__init__.py`（空文件）
- Create: `infrastructure/persistence/storyos/schemas/base.py`
- Create: `tests/unit/infrastructure/persistence/storyos/schemas/test_base_registry_schema.py`

- [ ] **Step 1: 写失败测试**

```python
from sqlalchemy import inspect
from infrastructure.persistence.database.connection import get_engine
from infrastructure.persistence.storyos.schemas.base import BaseRegistrySchema


def test_base_registry_schema_fields():
    """验证 mixin 定义了 9 个共用字段。"""
    expected_fields = {
        "id", "project_id", "created_chapter", "status",
        "description", "linked_assets", "cascade_updated_at",
        "created_at", "updated_at",
    }
    actual = {c.name for c in BaseRegistrySchema.__table__.columns}
    assert expected_fields.issubset(actual), f"missing: {expected_fields - actual}"


def test_base_registry_schema_no_tablename():
    """BaseRegistrySchema 是 mixin，不设置 __tablename__。"""
    # SQLAlchemy mixin 不应有 __tablename__；具体表设置自己的
    assert not hasattr(BaseRegistrySchema, "__tablename__") or BaseRegistrySchema.__tablename__ is None
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`（infrastructure.persistence.storyos 不存在）
- [ ] **Step 3: 实现** — `infrastructure/persistence/storyos/schemas/base.py`：

```python
"""BaseRegistrySchema — 11 张表共用的 mixin 字段。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column


class BaseRegistrySchema:
    """8 registry 表的共用 mixin（spec §3.4 锁定 9 字段）。

    字段：
        id: 业务主键（str）
        project_id: FK 到 novels
        created_chapter: 创建章节
        status: AssetStatus.value
        description: 描述
        linked_assets: JSON dict[str, str]
        cascade_updated_at: 最近一次级联更新时间
        created_at / updated_at: UTC 时间戳
    """

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    created_chapter: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    linked_assets: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    cascade_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

> **注意**：本文件 import `infrastructure.persistence.database.connection` 仅用于测试时的 engine；如该模块不存在请创建或调整 import 路径。

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed
- [ ] **Step 5: Commit** — `git add infrastructure/persistence/storyos/ tests/unit/infrastructure/persistence/storyos/ && git commit -m "feat(persistence): add BaseRegistrySchema mixin for 11 tables"`

#### Task D5: Schema 约定文档

**Files:**
- Create: `infrastructure/persistence/storyos/schemas/CONVENTIONS.md`

- [ ] **Step 1-4: 跳过**（**这是文档任务，无测试**）
- [ ] **Step 3: 写文档** — `infrastructure/persistence/storyos/schemas/CONVENTIONS.md`：

```markdown
# StoryOS Schema 约定

> **范围**: `infrastructure/persistence/storyos/schemas/*` 下所有 ORM schema 必须遵守。
> **目标读者**: 1B 仓储实现、1E 迁移脚本维护者。

## 表名规则

- 格式: `storyos_<entity>_v1`
- 例子: `storyos_conflict_v1`, `storyos_mystery_v1`, `storyos_foreshadowing_v1`
- 留 `_v1` 后缀：便于未来 schema 演进（v2 不破坏 v1 数据）

## 字段命名

- snake_case
- ID 字段: `<entity>_id`（如 `mystery_id`）
- 时间戳一律 UTC

## 主键

- **业务 ID**（`str`），不用自增 int
- 由调用方生成（UUID/业务规则 ID）

## 外键

- 声明外键约束但**不强制级联删除**
- 孤儿检查由 service 层负责（spec §4.2 锁定）

## 通用字段（来自 BaseRegistrySchema）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | str (PK) | 业务 ID |
| `project_id` | str (FK→novels, indexed) | 所属项目 |
| `created_chapter` | int | 创建章节 |
| `status` | str (indexed) | AssetStatus.value |
| `description` | str | 描述 |
| `linked_assets` | JSON (dict[str,str]) | 关联资产 ID 映射 |
| `cascade_updated_at` | datetime (nullable) | 最近一次级联更新 |
| `created_at` | datetime | UTC |
| `updated_at` | datetime | UTC，onupdate 自动 |

## 实体专属字段（不通用）

每个表有自己的字段（如 `intensity`, `involved_characters`）；这些字段**不**进 BaseRegistrySchema，
由具体 schema 文件定义。

## mapper 约定

- 文件命名: `<entity>_mapper.py`
- 暴露 `to_domain(row) -> Entity` 与 `to_orm(entity) -> Row` 双向方法
- 双向转换**对称**（测试覆盖）
- 旧→新状态映射（如 Foreshadowing）由 mapper 的 `convert_old_status_to_new` 静态方法提供
```

- [ ] **Step 5: Commit** — `git add infrastructure/persistence/storyos/schemas/CONVENTIONS.md && git commit -m "docs(persistence): document storyos schema conventions"`

---

### Group E: 11 Schemas + Mappers（3 任务，批处理）

> 每个 schema 必须继承 `BaseRegistrySchema` 并设置 `__tablename__`。mapper 必须 `to_domain` / `to_orm` 双向对称。

#### Task E1: Conflict + Mystery + Twist + Promise schemas + mappers

**Files:**
- Create: `infrastructure/persistence/storyos/schemas/conflict_schema.py`
- Create: `infrastructure/persistence/storyos/schemas/mystery_schema.py`
- Create: `infrastructure/persistence/storyos/schemas/twist_schema.py`
- Create: `infrastructure/persistence/storyos/schemas/promise_schema.py`
- Create: `infrastructure/persistence/storyos/mappers/__init__.py`（空文件）
- Create: `infrastructure/persistence/storyos/mappers/conflict_mapper.py`
- Create: `infrastructure/persistence/storyos/mappers/mystery_mapper.py`
- Create: `infrastructure/persistence/storyos/mappers/twist_mapper.py`
- Create: `infrastructure/persistence/storyos/mappers/promise_mapper.py`
- Create: `tests/unit/infrastructure/persistence/storyos/schemas/test_first_batch_schemas.py`
- Create: `tests/unit/infrastructure/persistence/storyos/mappers/test_first_batch_mappers.py`

- [ ] **Step 1: 写失败测试** — `tests/unit/infrastructure/persistence/storyos/schemas/test_first_batch_schemas.py`：

```python
from sqlalchemy import inspect
from infrastructure.persistence.storyos.schemas.conflict_schema import ConflictSchema
from infrastructure.persistence.storyos.schemas.mystery_schema import MysterySchema
from infrastructure.persistence.storyos.schemas.twist_schema import TwistSchema
from infrastructure.persistence.storyos.schemas.promise_schema import PromiseSchema
from infrastructure.persistence.storyos.schemas.base import BaseRegistrySchema


def test_conflict_schema_tablename():
    assert ConflictSchema.__tablename__ == "storyos_conflict_v1"


def test_mystery_schema_tablename():
    assert MysterySchema.__tablename__ == "storyos_mystery_v1"


def test_twist_schema_tablename():
    assert TwistSchema.__tablename__ == "storyos_twist_v1"


def test_promise_schema_tablename():
    assert PromiseSchema.__tablename__ == "storyos_promise_v1"


def test_all_schemas_inherit_base():
    for cls in (ConflictSchema, MysterySchema, TwistSchema, PromiseSchema):
        assert issubclass(cls, BaseRegistrySchema)


def test_conflict_has_intensity_and_characters():
    cols = {c.name for c in ConflictSchema.__table__.columns}
    assert "intensity" in cols
    assert "involved_characters" in cols


def test_mystery_has_clues():
    cols = {c.name for c in MysterySchema.__table__.columns}
    assert "clues" in cols
    assert "related_mystery" in cols


def test_twist_has_twist_type():
    cols = {c.name for c in TwistSchema.__table__.columns}
    assert "twist_type" in cols
    assert "forbidden_concurrent" in cols


def test_promise_has_importance():
    cols = {c.name for c in PromiseSchema.__table__.columns}
    assert "importance" in cols
```

`tests/unit/infrastructure/persistence/storyos/mappers/test_first_batch_mappers.py`：

```python
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.entities.mystery import Clue, Mystery
from domain.storyos.entities.twist import Twist, TwistType
from domain.storyos.entities.promise import Promise
from infrastructure.persistence.storyos.mappers.conflict_mapper import ConflictMapper
from infrastructure.persistence.storyos.mappers.mystery_mapper import MysteryMapper
from infrastructure.persistence.storyos.mappers.twist_mapper import TwistMapper
from infrastructure.persistence.storyos.mappers.promise_mapper import PromiseMapper


def test_conflict_round_trip():
    c = Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.MEDIUM, status=AssetStatus.ACTIVE,
        involved_characters=("a", "b"), created_chapter=1,
    )
    row = ConflictMapper.to_orm(c)
    c2 = ConflictMapper.to_domain(row)
    assert c2 == c


def test_mystery_round_trip_with_clues():
    cl = Clue(id="cl1", mystery_id="m1", description="a",
              source_chapter=1, source_location="x")
    m = Mystery(
        id="m1", novel_id="n1", description="x",
        status=AssetStatus.PLANTED, created_chapter=1, clues=(cl,),
    )
    row = MysteryMapper.to_orm(m)
    m2 = MysteryMapper.to_domain(row)
    assert m2.clues == m.clues
    assert m2.id == m.id


def test_twist_round_trip():
    t = Twist(
        id="t1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1,
        twist_type=TwistType.IDENTITY_REVEAL,
        reveal_trigger="mystery:m1:revealed",
    )
    row = TwistMapper.to_orm(t)
    t2 = TwistMapper.to_domain(row)
    assert t2 == t


def test_promise_round_trip():
    p = Promise(
        id="p1", novel_id="n1", description="x",
        made_in_chapter=1, status=AssetStatus.ACTIVE, importance=80,
    )
    row = PromiseMapper.to_orm(p)
    p2 = PromiseMapper.to_domain(row)
    assert p2 == p
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现 4 schemas + 4 mappers**（参考模板）：

`infrastructure/persistence/storyos/schemas/conflict_schema.py`：

```python
from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase

from infrastructure.persistence.storyos.schemas.base import BaseRegistrySchema


class ConflictSchema(BaseRegistrySchema, DeclarativeBase):
    __tablename__ = "storyos_conflict_v1"

    intensity: Mapped[str] = mapped_column(String)
    involved_characters: Mapped[list[str]] = mapped_column(JSON, default=list)
```

`infrastructure/persistence/storyos/mappers/conflict_mapper.py`：

```python
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from infrastructure.persistence.storyos.schemas.conflict_schema import ConflictSchema


class ConflictMapper:
    @staticmethod
    def to_orm(c: Conflict) -> ConflictSchema:
        row = ConflictSchema(
            id=c.id,
            project_id=c.novel_id,
            created_chapter=c.created_chapter,
            status=c.status.value,
            description=c.description,
            linked_assets={},
            intensity=c.intensity.name,
            involved_characters=list(c.involved_characters),
        )
        return row

    @staticmethod
    def to_domain(row: ConflictSchema) -> Conflict:
        return Conflict(
            id=row.id,
            novel_id=row.project_id,
            description=row.description,
            intensity=ConflictIntensity[row.intensity],
            status=AssetStatus(row.status),
            involved_characters=tuple(row.involved_characters or []),
            created_chapter=row.created_chapter,
        )
```

> **剩余 3 schemas/mappers** 按相同模式实现（字段名见 test_first_batch_schemas.py 断言）。Mystery 的 clues 用 `JSON` 存 `list[dict]`（clue 字段序列化为 dict）；Promise 的 importance 存 int；Twist 的 twist_type 存 str，forbidden_concurrent 存 `list[str]`。

- [ ] **Step 4: 运行测试确认通过** — 期望 schema 8 passed + mapper 4 passed
- [ ] **Step 5: Commit** — `git add infrastructure/persistence/storyos/ tests/unit/infrastructure/persistence/storyos/ && git commit -m "feat(persistence): add Conflict/Mystery/Twist/Promise schemas + mappers"`

#### Task E2: Reveal + Expectation + Goal + Foreshadowing schemas + mappers

**Files:**
- Create: `infrastructure/persistence/storyos/schemas/reveal_schema.py`
- Create: `infrastructure/persistence/storyos/schemas/expectation_schema.py`
- Create: `infrastructure/persistence/storyos/schemas/goal_schema.py`
- Create: `infrastructure/persistence/storyos/schemas/foreshadowing_schema.py`
- Create: `infrastructure/persistence/storyos/mappers/reveal_mapper.py`
- Create: `infrastructure/persistence/storyos/mappers/expectation_mapper.py`
- Create: `infrastructure/persistence/storyos/mappers/goal_mapper.py`
- Create: `infrastructure/persistence/storyos/mappers/foreshadowing_mapper.py`（**含 `convert_old_status_to_new`**）
- Create: `tests/unit/infrastructure/persistence/storyos/schemas/test_second_batch_schemas.py`
- Create: `tests/unit/infrastructure/persistence/storyos/mappers/test_second_batch_mappers.py`

- [ ] **Step 1: 写失败测试** — schema 测试同 E1 模式（验证 4 个表名 + 实体专属字段）。mapper 测试覆盖双向 round-trip，**ForeshadowingMapper 额外测试**：

```python
from domain.storyos.contracts import AssetStatus
from infrastructure.persistence.storyos.mappers.foreshadowing_mapper import ForeshadowingMapper


def test_convert_old_status_to_new_planted():
    assert ForeshadowingMapper.convert_old_status_to_new("planted") == AssetStatus.PLANTED


def test_convert_old_status_to_new_resolved():
    assert ForeshadowingMapper.convert_old_status_to_new("resolved") == AssetStatus.REVEALED


def test_convert_old_status_to_new_abandoned():
    assert ForeshadowingMapper.convert_old_status_to_new("abandoned") == AssetStatus.DEAD


def test_convert_old_status_to_new_unknown_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown old foreshadowing status"):
        ForeshadowingMapper.convert_old_status_to_new("unknown")
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ImportError`
- [ ] **Step 3: 实现 4 schemas + 4 mappers**（模式同 E1）。ForeshadowingMapper 关键方法：

```python
class ForeshadowingMapper:
    # spec 附录 C 锁定
    _OLD_TO_NEW = {
        "planted": AssetStatus.PLANTED,
        "resolved": AssetStatus.REVEALED,
        "abandoned": AssetStatus.DEAD,
    }

    @staticmethod
    def convert_old_status_to_new(old: str) -> AssetStatus:
        if old not in ForeshadowingMapper._OLD_TO_NEW:
            raise ValueError(f"Unknown old foreshadowing status: {old!r}")
        return ForeshadowingMapper._OLD_TO_NEW[old]

    @staticmethod
    def to_orm(f) -> ForeshadowingSchema:
        return ForeshadowingSchema(
            id=f.id, project_id=f.novel_id, created_chapter=f.planted_in_chapter,
            status=f.status.value, description=f.description,
            linked_assets={}, importance=f.importance.name,
            suggested_resolve_chapter=f.suggested_resolve_chapter,
            resolved_in_chapter=f.resolved_in_chapter,
        )

    @staticmethod
    def to_domain(row) -> Foreshadowing:
        from domain.novel.value_objects.foreshadowing import ImportanceLevel
        return Foreshadowing(
            id=row.id, novel_id=row.project_id, description=row.description,
            importance=ImportanceLevel[row.importance], status=AssetStatus(row.status),
            planted_in_chapter=row.created_chapter,
            suggested_resolve_chapter=row.suggested_resolve_chapter,
            resolved_in_chapter=row.resolved_in_chapter,
        )
```

- [ ] **Step 4: 运行测试确认通过** — 期望所有 schema/mapper 测试通过
- [ ] **Step 5: Commit** — `git add infrastructure/persistence/storyos/ tests/unit/infrastructure/persistence/storyos/ && git commit -m "feat(persistence): add Reveal/Expectation/Goal/Foreshadowing schemas + mappers"`

#### Task E3: cascade_history + sflog_event + bridge_log schemas + mappers

**Files:**
- Create: `infrastructure/persistence/storyos/schemas/cascade_history_schema.py`
- Create: `infrastructure/persistence/storyos/schemas/sflog_event_schema.py`
- Create: `infrastructure/persistence/storyos/schemas/bridge_log_schema.py`（⚡ bridge 事务外写）
- Create: `infrastructure/persistence/storyos/mappers/cascade_history_mapper.py`
- Create: `infrastructure/persistence/storyos/mappers/sflog_event_mapper.py`
- Create: `infrastructure/persistence/storyos/mappers/bridge_log_mapper.py`
- Create: `tests/unit/infrastructure/persistence/storyos/schemas/test_audit_schemas.py`
- Create: `tests/unit/infrastructure/persistence/storyos/mappers/test_audit_mappers.py`

- [ ] **Step 1: 写失败测试** — 3 个 schema 共用模式：

```python
from infrastructure.persistence.storyos.schemas.cascade_history_schema import CascadeHistorySchema
from infrastructure.persistence.storyos.schemas.sflog_event_schema import SFLogEventSchema
from infrastructure.persistence.storyos.schemas.bridge_log_schema import BridgeLogSchema


def test_cascade_history_tablename():
    assert CascadeHistorySchema.__tablename__ == "storyos_cascade_history_v1"


def test_sflog_event_tablename():
    assert SFLogEventSchema.__tablename__ == "storyos_sflog_event_v1"


def test_bridge_log_tablename():
    assert BridgeLogSchema.__tablename__ == "storyos_bridge_log_v1"


def test_cascade_history_fields():
    cols = {c.name for c in CascadeHistorySchema.__table__.columns}
    expected = {"id", "project_id", "chapter_id", "trigger",
                "source_asset_type", "source_asset_id", "target_asset_type",
                "target_asset_id", "executed", "blocked_reason", "executed_at"}
    assert expected.issubset(cols)


def test_sflog_event_fields():
    cols = {c.name for c in SFLogEventSchema.__table__.columns}
    expected = {"id", "project_id", "chapter_id", "raw_text", "log_type",
                "status", "params", "error"}
    assert expected.issubset(cols)


def test_bridge_log_fields():
    """bridge_log 是 ⚡ 关键表：记录 bridge 失败聚合（在事务外写）。"""
    cols = {c.name for c in BridgeLogSchema.__table__.columns}
    expected = {"id", "project_id", "chapter_id", "transaction_id",
                "evolution_actions_count", "registry_updates_count",
                "cascade_steps_count", "success", "error", "duration_ms", "created_at"}
    assert expected.issubset(cols)
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现 3 schemas + 3 mappers**（模式同 E1/E2）。`bridge_log_schema.py` 关键字段：

```python
from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase


class BridgeLogSchema(DeclarativeBase):
    __tablename__ = "storyos_bridge_log_v1"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, index=True)
    chapter_id: Mapped[int] = mapped_column(Integer, index=True)
    transaction_id: Mapped[str] = mapped_column(String)
    evolution_actions_count: Mapped[int] = mapped_column(Integer)
    registry_updates_count: Mapped[int] = mapped_column(Integer)
    cascade_steps_count: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

> **⚠️ 设计笔记**：`bridge_log` 是 spec §3.4 ⚡ 标记的关键表。它在 bridge 事务**外**写入，专门记录 bridge 失败聚合——因为 sflog_event 在事务内会随 ROLLBACK 回滚，无法用于事后排查。

- [ ] **Step 4: 运行测试确认通过** — 期望所有测试通过
- [ ] **Step 5: Commit** — `git add infrastructure/persistence/storyos/ tests/unit/infrastructure/persistence/storyos/ && git commit -m "feat(persistence): add cascade_history/sflog_event/bridge_log schemas + mappers (⚡ bridge_log)"`

---

### Group F: 迁移（2 任务）

#### Task F1: Alembic 迁移 `0001_storyos_init.py`

**Files:**
- Create: `infrastructure/persistence/database/migrations/versions/0001_storyos_init.py`
- Create: `tests/unit/infrastructure/persistence/database/migrations/test_storyos_init_migration.py`

- [ ] **Step 1: 写失败测试**

```python
import sqlite3
from pathlib import Path
import subprocess


def test_alembic_upgrade_creates_11_tables(tmp_path):
    """alembic upgrade head 后 11 张表存在。"""
    db_path = tmp_path / "test.db"
    # 1A 范围：手动执行迁移（不依赖 alembic 环境配置）
    from infrastructure.persistence.database.connection import init_db
    # 调用迁移文件中的 upgrade 函数
    from infrastructure.persistence.database.migrations.versions import storyos_init_0001
    conn = sqlite3.connect(str(db_path))
    try:
        storyos_init_0001.upgrade(conn)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'storyos_%'"
        )
        tables = {row[0] for row in cur.fetchall()}
        expected_tables = {
            "storyos_conflict_v1", "storyos_mystery_v1", "storyos_twist_v1",
            "storyos_promise_v1", "storyos_reveal_v1", "storyos_expectation_v1",
            "storyos_goal_v1", "storyos_foreshadowing_v1",
            "storyos_cascade_history_v1", "storyos_sflog_event_v1",
            "storyos_bridge_log_v1",
        }
        assert expected_tables.issubset(tables), f"missing: {expected_tables - tables}"
    finally:
        conn.close()


def test_alembic_downgrade_drops_all(tmp_path):
    """downgrade 应删除所有 11 张表。"""
    db_path = tmp_path / "test.db"
    from infrastructure.persistence.database.migrations.versions import storyos_init_0001
    conn = sqlite3.connect(str(db_path))
    try:
        storyos_init_0001.upgrade(conn)
        storyos_init_0001.downgrade(conn)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'storyos_%'"
        )
        tables = {row[0] for row in cur.fetchall()}
        assert tables == set()
    finally:
        conn.close()
```

> **注意**：1A 阶段不强制走完整 alembic upgrade 流程；测试通过直接调用 `upgrade(conn)` / `downgrade(conn)` 函数验证逻辑。完整 alembic 配置在 1E 阶段补完。

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `infrastructure/persistence/database/migrations/versions/0001_storyos_init.py`（或 `storyos_init_0001.py`，1A 阶段用模块名以方便测试直接 import）：

```python
"""Alembic 迁移：0001_storyos_init — 创建 11 张 storyos 表。"""
from __future__ import annotations

import sqlite3


def upgrade(conn: sqlite3.Connection) -> None:
    """创建 11 张表。"""
    _create_conflict(conn)
    _create_mystery(conn)
    _create_twist(conn)
    _create_promise(conn)
    _create_reveal(conn)
    _create_expectation(conn)
    _create_goal(conn)
    _create_foreshadowing(conn)
    _create_cascade_history(conn)
    _create_sflog_event(conn)
    _create_bridge_log(conn)


def downgrade(conn: sqlite3.Connection) -> None:
    """删除所有 11 张表。"""
    for table in [
        "storyos_conflict_v1", "storyos_mystery_v1", "storyos_twist_v1",
        "storyos_promise_v1", "storyos_reveal_v1", "storyos_expectation_v1",
        "storyos_goal_v1", "storyos_foreshadowing_v1",
        "storyos_cascade_history_v1", "storyos_sflog_event_v1",
        "storyos_bridge_log_v1",
    ]:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()


def _create_conflict(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS storyos_conflict_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_chapter INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT NOT NULL,
            linked_assets TEXT NOT NULL DEFAULT '{}',
            cascade_updated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            intensity TEXT NOT NULL,
            involved_characters TEXT NOT NULL DEFAULT '[]'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_storyos_conflict_v1_project_id ON storyos_conflict_v1(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_storyos_conflict_v1_status ON storyos_conflict_v1(status)")
    conn.commit()


# _create_mystery / _create_twist / ... 按相同模式实现（共 8 张 registry + 3 张 audit）
# 完整实现参见 1A 实施时填充；所有表都包含 BaseRegistrySchema 9 字段 + 实体专属字段
```

> 完整实现所有 `_create_*` 函数（共 11 个）；每张表都有 9 个共用字段 + 实体专属字段 + `project_id` / `status` 索引。

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed
- [ ] **Step 5: Commit** — `git add infrastructure/persistence/database/migrations/ tests/unit/infrastructure/persistence/database/migrations/ && git commit -m "feat(migration): add 0001_storyos_init creating 11 tables"`

#### Task F2: scripts/migrate_storyos.py CLI 脚手架

**Files:**
- Create: `scripts/migrate_storyos.py`
- Create: `tests/integration/scripts/test_migrate_storyos_cli.py`

- [ ] **Step 1: 写失败测试**

```python
import subprocess
import sys


def test_cli_help_exit_zero():
    """python scripts/migrate_storyos.py --help 应退出码 0。"""
    result = subprocess.run(
        [sys.executable, "scripts/migrate_storyos.py", "--help"],
        capture_output=True, text=True, cwd="/Users/longsa/Codes/plotPilot",
    )
    assert result.returncode == 0


def test_cli_help_shows_subcommands():
    """--help 应显示 dry-run / execute / rollback 三个子命令。"""
    result = subprocess.run(
        [sys.executable, "scripts/migrate_storyos.py", "--help"],
        capture_output=True, text=True, cwd="/Users/longsa/Codes/plotPilot",
    )
    assert "dry-run" in result.stdout
    assert "execute" in result.stdout
    assert "rollback" in result.stdout
```

- [ ] **Step 2: 运行 CLI** — 期望 `ModuleNotFoundError` 或 `argparse: error`
- [ ] **Step 3: 实现** — `scripts/migrate_storyos.py`：

```python
"""StoryOS 数据迁移 CLI（1A 脚手架，1E 补完业务逻辑）。

子命令：
    --dry-run    扫描 + 报告，不写入
    --execute    实际迁移（带断点续跑）
    --rollback   回滚（基于迁移日志）
"""
from __future__ import annotations

import argparse
import sys


def cmd_dry_run(args) -> int:
    raise NotImplementedError("完整实现在 Phase 1E")


def cmd_execute(args) -> int:
    raise NotImplementedError("完整实现在 Phase 1E")


def cmd_rollback(args) -> int:
    raise NotImplementedError("完整实现在 Phase 1E")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="migrate_storyos",
        description="StoryOS 数据迁移 CLI（1A 脚手架，1E 补完业务逻辑）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_dry = sub.add_parser("dry-run", help="扫描 + 报告，不写入")
    p_dry.set_defaults(func=cmd_dry_run)

    p_exec = sub.add_parser("execute", help="实际迁移（带断点续跑）")
    p_exec.set_defaults(func=cmd_execute)

    p_rb = sub.add_parser("rollback", help="回滚（基于迁移日志）")
    p_rb.add_argument("--to", required=True, help="回滚到指定 migration_id")
    p_rb.set_defaults(func=cmd_rollback)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行 CLI --help** — 期望显示三子命令
- [ ] **Step 5: Commit** — `git add scripts/migrate_storyos.py tests/integration/scripts/test_migrate_storyos_cli.py && git commit -m "feat(scripts): scaffold migrate_storyos.py CLI (1E completes logic)"`

> **⚠️ 范围限制**：F2 只交付 CLI 框架。`dry-run/execute/rollback` 的业务逻辑由 1E 实现。

---

## 4. 关键设计决策（影响后续阶段）

### 4.1 WriteDispatch 向后兼容（风险 #5 缓解）

**问题**：现有调用方大量使用 `dispatch.queue(lambda c: ...)`。如破坏签名，回归测试大面积失败。

**本阶段对策**：
- `queue()` 旧方法**保留**，签名不变
- 新增 `queue_apply()` 是**可选**增强，不替代 `queue()`
- `transaction()` 是**新增**入口，不替代现有 `dispatch` 直发模式

**验证**：运行 `pytest tests/ -m "not slow"` 全部通过 → 写入迁移检查 `grep -r "dispatch.queue" interfaces/ application/ | wc -l` 与 baseline 对比。

### 4.2 bridge_log 写入时机

`bridge_log` 写入**不在** `transaction()` 内部。原因：
- 事务内写入会随 ROLLBACK 回滚 → 失败记录丢失
- `bridge_log` 是**事后审计**，需在事务外另起一个 `dispatch.queue_apply()` 单写

**实现约定**（在 1B `EvolutionBridgeService` 落实）：

```python
# 1B 阶段伪代码（演示新 queue_apply API）
try:
    with dispatch.transaction() as txn:
        txn.queue_apply(evolution_apply, actions, novel_id)        # 参数立即绑定
        txn.queue_apply(registry_apply_with_cascade, updates, novel_id)
        txn.queue_apply(sflog_event_record, records, novel_id)
except BridgeError as e:
    # bridge_log 写在事务外——避免 ROLLBACK 时审计丢失
    dispatch.queue_apply(bridge_log_record, success=False, error=str(e))
    raise
```

### 4.3 Foreshadowing 旧表不删除

`domain/novel/value_objects/foreshadowing.py` 与 `domain/novel/entities/foreshadowing_registry.py` **保留**至 Phase 2。理由：
- 旧 API 仍被外部使用（snapshot_service、state_updater 等）
- 1A 仅**新增** `domain/storyos/entities/foreshadowing.py`
- 1E 创建迁移脚本时，**旧表只读**，新表写新
- Phase 2 spec 决定彻底切换/删除

### 4.4 Schema 命名约定

- 表名：`storyos_<entity>_v1`（如 `storyos_conflict_v1`）
- 留 `_v1` 后缀便于未来 schema 演进
- mapper 名称：`<entity>_mapper.py` 与 schema 同名

### 4.5 DDD 分层 — Clue 投影延迟到 1B

sub-spec §3.6 修正：`Clue.to_revealed_clue_item()` **不**在 1A 实现。
- 原因：`to_revealed_clue_item()` 需要 import `application.engine.services.memory_engine.RevealedClueItem`，违反 domain 不依赖 application 的分层规则
- 替代：1B `MysteryService` 注入 `RevealedClueItem` 工厂方法，在 Clue 状态变更时调用
- 投影字段映射见 sub-spec §3.5

---

## 5. 风险 + 本阶段缓解映射

| 风险 | 等级 | 本阶段缓解任务 |
|---|---|---|
| #5 CircuitBreaker 扩展破坏向后兼容 | 🟢 低 | D1/D2/D3（WriteDispatch 扩展 + 完整回归测试） |
| Bridge 双写并发竞争 | 🟡 中 | D3（mock 异常场景 + 完整回滚验证） |
| Migration 数据不一致 | 🟡 中 | F1（upgrade/downgrade roundtrip 测试） |

LLM 合规性（风险 #1）和 Cascade 性能（风险 #4）的缓解任务在 1B 实施。

---

## 6. 完成判据

### 6.1 功能验收（100% 必须通过）

- [ ] A1-A5：5 个枚举/协议测试全过
- [ ] B1-B5：5 个值对象测试全过（含 `PredeclaredChange` XOR 校验、`MatchReport` properties、`SFLogRecord` 6 字段）
- [ ] C1-C8：8 个实体测试全过（含 `TwistType` 6 值、`Clue` 9 字段 + 状态转换、Foreshadowing 新位置可构造）
- [ ] D1-D3：WriteDispatch 扩展测试全过（向后兼容 + 原子性 + queue_apply 闭包陷阱修复）
- [ ] D4-D5：Base mixin + schema 约定文档
- [ ] E1-E3：11 张表 schema + 11 个 mapper 测试全过
- [ ] F1：upgrade/downgrade 双向 roundtrip 通过
- [ ] F2：CLI 脚手架 `--help` 退出码 0
- [ ] `pytest tests/ -m "not slow"` 全过（向后兼容验证）

### 6.2 性能基准（1A 范围内）

| 测试 | 期望 |
|---|---|
| `test_persistence_schema_creation` | 11 张表创建 < 200ms |
| `test_mapper_round_trip` | 8 实体 × 1000 次 round-trip < 1s |

### 6.3 阶段输出交接清单（给 1B）

- [ ] `domain/storyos/` 子包可被 `application/storyos/` 引用
- [ ] `from domain.storyos.contracts import AssetStatus, SFLogType, CascadeTrigger` 可导入
- [ ] `from domain.storyos.value_objects.predeclared import PredeclaredChange, MatchReport` 可导入
- [ ] `from domain.storyos.value_objects.sf_log import SFLogRecord, SFLogParam` 可导入
- [ ] `from infrastructure.persistence.database.write_dispatch import WriteDispatch, WriteTransaction` 含 `transaction()` 与 `queue_apply()`
- [ ] 11 张表已可创建（`upgrade()` 函数测试通过）
- [ ] `scripts/migrate_storyos.py --help` 显示三子命令

---

## 7. 任务统计

| Group | 任务数 | 关键产出 |
|---|---|---|
| A: Domain Contracts | 5 | 3 枚举 + 1 协议 + 1 常量 + FORBIDDEN_TRANSITIONS |
| B: Value Objects | 5 | SFLogRecord/CascadeStep/CascadeRules/PredeclaredChange/MatchReport+FormatError |
| C: 8 Entities | 8 | 8 narrative asset 实体（含 Clue 9 字段、TwistType 6 值） |
| D: Persistence Infra | 5 | WriteDispatch 扩展 + Base mixin + 约定文档 |
| E: 11 Schemas + Mappers | 3 | 22 文件（11 schema + 11 mapper）+ 子包 `__init__.py` |
| F: Migration | 2 | alembic 迁移 + CLI 脚手架 |
| **合计** | **28** | **~50 新文件 + 1 修改**（write_dispatch.py），~3500 LOC |

**文件清单**：
- Domain: 1 contracts.py + 5 value_objects/*.py + 8 entities/*.py + 3 `__init__.py` = 17 新文件
- Persistence: 1 base.py + 11 schemas/*.py + 11 mappers/*.py + 4 `__init__.py` + 1 CONVENTIONS.md = 28 新文件
- Infrastructure: 1 alembic migration + 1 CLI script = 2 新文件
- Tests: ~28 test files
- **Modified**: 1 write_dispatch.py
- **Total**: ~50 新文件 + 1 修改

---

## 8. 执行模式

### 8.1 推荐：Subagent-Driven

1A 适合 subagent-driven：每组（Group A-F）可派 1 个 subagent，subagent 之间通过 git 提交契约衔接。

**关键契约交接点**：
- Group A 完成后 → Group B/C 可启动（依赖 AssetStatus 等枚举）
- Group C 完成后 → Group D 可启动（实体构造测试需要实体存在）
- Group D 完成后 → Group E 可启动（schema 测试需要 BaseRegistrySchema）
- Group E 完成后 → Group F 可启动（迁移测试需要 schemas 存在）

### 8.2 备选：Inline Execution

按 A1-A5 → B1-B5 → C1-C8 → D1-D5 → E1-E3 → F1-F2 顺序，每完成一组做 checkpoint review。

---

## 9. 进度追踪

| 任务 | 状态 | Commit | 备注 |
|---|---|---|---|
| A1 AssetStatus | ⬜ 待开始 | | |
| A2 SFLogType | ⬜ 待开始 | | |
| A3 CascadeTrigger | ⬜ 待开始 | | |
| A4 FORBIDDEN_TRANSITIONS | ⬜ 待开始 | | |
| A5 RegistryAsset Protocol | ⬜ 待开始 | | |
| B1 SFLogRecord | ⬜ 待开始 | | sub-spec §1 |
| B2 CascadeStep | ⬜ 待开始 | | |
| B3 CascadeRules | ⬜ 待开始 | | |
| B4 PredeclaredChange | ⬜ 待开始 | | |
| B5 MatchReport+FormatError | ⬜ 待开始 | | |
| C1 Conflict | ⬜ 待开始 | | |
| C2 Mystery + Clue | ⬜ 待开始 | | sub-spec §3 |
| C3 Twist + TwistType | ⬜ 待开始 | | sub-spec §2 |
| C4 Promise | ⬜ 待开始 | | |
| C5 Reveal | ⬜ 待开始 | | |
| C6 Expectation | ⬜ 待开始 | | |
| C7 Goal + ProgressMarker | ⬜ 待开始 | | |
| C8 Foreshadowing | ⬜ 待开始 | | 旧表保留 |
| D1 WriteTransaction 类 | ⬜ 待开始 | | |
| D2 transaction() ctx mgr | ⬜ 待开始 | | |
| D3 queue_apply + 原子性 | ⬜ 待开始 | | ⚠️ 关键 |
| D4 BaseRegistrySchema | ⬜ 待开始 | | |
| D5 Schema 约定文档 | ⬜ 待开始 | | |
| E1 4 实体 schema+mapper | ⬜ 待开始 | | |
| E2 4 实体 schema+mapper | ⬜ 待开始 | | ForeshadowingMapper 含 convert_old_status_to_new |
| E3 3 audit schema+mapper | ⬜ 待开始 | | 含 ⚡ bridge_log |
| F1 alembic 迁移 | ⬜ 待开始 | | |
| F2 migrate_storyos.py 脚手架 | ⬜ 待开始 | | 1E 补完 |

---

## 10. 设计参考

- **Spec 主参考**：`../specs/2026-07-02-storyos-integration-design.md`
  - §3.1 文件清单
  - §3.2 类型签名（AssetStatus/PredeclaredChange/CascadeTrigger/CascadeStep/BridgeResult）
  - §3.4 11 张表（schema 共用模板）
  - §3.5 WriteDispatch 扩展
  - 附录 C Foreshadowing 状态映射
- **Sub-Spec**：`../specs/2026-07-02-storyos-asset-field-spec.md`
  - §1 SFLogRecord 6 字段（log_type/params/raw/chapter_id/char_position/asset_id）
  - §2 TwistType 6 值（IDENTITY_REVEAL/BETRAYAL/FORTUNE_REVERSAL/WORLD_RULE_REVEAL/SACRIFICE/TRUTH_REVEALED）
  - §3 Clue 9 字段 + ClueCategory + 与 RevealedClueItem 关系
  - §3.6 修正：`Clue.to_revealed_clue_item()` 延迟到 1B
- **现有 Foreshadowing 旧代码**：
  - `domain/novel/value_objects/foreshadowing.py`（旧位置，本阶段不删）
  - `domain/novel/entities/foreshadowing_registry.py`
  - `domain/novel/repositories/foreshadowing_repository.py`
  - `infrastructure/persistence/mappers/foreshadowing_mapper.py`
- **现有 RevealedClueItem**：`application/engine/services/memory_engine.py:70-84`
- **WriteDispatch 现有 API**：`infrastructure/persistence/database/write_dispatch.py`
- **CircuitBreaker 现有 API**（1B 才扩展）：`application/engine/services/circuit_breaker.py`
- **ScenePlan 现有定义**（1C 才扩展）：`engine/pipeline/beat_contracts.py`
- **1B 阶段产出（消费本阶段）**：`./2026-07-02-storyos-phase-1b-application.md`
- **1E 阶段产出（消费本阶段）**：`./2026-07-02-storyos-phase-1e-migration.md`
