# StoryOS Asset Field Specification (Sub-Spec)

> **Scope:** 本文档是 [`2026-07-02-storyos-integration-design.md`](./2026-07-02-storyos-integration-design.md) 的**子 spec**，锁定 domain entity / value object 的**内部字段设计**。主 spec 覆盖架构、cascade 规则、SF_LOG 标签语法；本子 spec 覆盖每个类型的字段集、类型、约束、跨 bounded context 关系。
>
> **目标版本:** PlotPilot v1.2 (Phase 1)
>
> **状态:** Draft → 待用户 review

---

## 0. 背景

主 spec（`2026-07-02-storyos-integration-design.md`）§3.2 锁定了 4 个关键类型签名（`AssetStatus` / `PredeclaredChange` / `CascadeTrigger` / `BridgeResult`），但**未**深入以下 3 个设计选择：

1. `SFLogRecord` 字段集 — §3.1 文件清单提到但 §3.2 类型表跳过
2. `TwistType` 成员 — spec 从未定义取值
3. `Clue` 字段集 — spec §3.1 + §4.2 + 附录 A 未定义；且与 PlotPilot 现有 `RevealedClueItem` 概念重叠

本子 spec 填补这 3 个空白，作为 1A Foundation 实施的**权威参考**。

---

## 1. SFLogRecord + SFLogParam（domain/storyos/value_objects/sf_log.py）

### 1.1 设计原则

- **`params` 用 `dict[str, str]`**：所有 SF_LOG 参数以字符串形式保存，类型转换在 parser 层（1B）做。理由：11 类 SF_LOG 参数类型异构（enum/int/str），强类型 union 会让 1A 阶段代码复杂 3-5 倍，1B parser 已有 Pydantic 校验层做转换。
- **`raw: str` 必填**：保留原始 HTML 注释文本（含 `<!-- SF_LOG ... -->` 包装），供审计与 `SFLogInspector` 前端展示。
- **`char_position: int` 是字符级偏移**：在章节文本中的字符位置，从 0 开始。前端 `SFLogInspector` 用此高亮跳转。
- **`asset_id: str | None`**：当 SF_LOG 是单资产操作（如 `mystery_clue id="..."`）时填写；关系型 SF_LOG（如 `character_relation_change char_a/char_b`）不填。

### 1.2 完整类型定义

```python
from typing import Any
from pydantic import BaseModel, ConfigDict
from domain.storyos.contracts import SFLogType


class SFLogParam(BaseModel):
    """SF_LOG 单个参数（key=value 解析结果）"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    value: str


class SFLogRecord(BaseModel):
    """从章节文本中提取的单条 SF_LOG 记录"""
    model_config = ConfigDict(extra="forbid", frozen=True)

    log_type: SFLogType
    params: dict[str, str]                     # 所有参数统一为字符串
    raw: str                                   # 原始 HTML 注释文本（含 <!-- SF_LOG ... -->）
    chapter_id: int                            # 所属章节
    char_position: int                         # 在章节文本中的字符偏移
    asset_id: str | None = None                # 单资产操作的资产 ID（关系型为 None）

    def get_param(self, key: str, default: str | None = None) -> str | None:
        """便捷获取参数（1B parser 会用）"""
        return self.params.get(key, default)

    def get_required_param(self, key: str) -> str:
        """获取必填参数，缺失抛 ValueError"""
        if key not in self.params:
            raise ValueError(f"SFLogRecord requires param '{key}' for log_type {self.log_type.value}")
        return self.params[key]
```

### 1.3 字段约束

| 字段 | 约束 | 验证时机 |
|---|---|---|
| `chapter_id` | `>= 1` | `__post_init__`（Pydantic 自动） |
| `char_position` | `>= 0` | `__post_init__` |
| `params` | 非空 dict（至少 1 个参数） | `__post_init__` |
| `raw` | 非空字符串 | Pydantic 自动 |
| `asset_id` | 当 `log_type` 是单资产型时必填；关系型时为 None | 1B parser 层（不归 1A） |

### 1.4 1A 范围

1A 仅定义类型与基础方法（`get_param` / `get_required_param`）。**类型校验与 log_type 字段必填规则留给 1B parser**（spec §3.3 的 11 类 SF_LOG → 6 映射 + 5 跳过逻辑在 1B）。

### 1.5 1B 消费

- `sf_log_regex_parser.py` 解析 `<!-- SF_LOG ... -->` 文本 → 构造 `SFLogRecord`
- `sf_log_format_validator.py` 用 `log_type` 与 `params` 必填规则校验
- `sf_log_action_mapper.py` 调用 `get_required_param` 取参数

---

## 2. TwistType 成员（domain/storyos/entities/twist.py）

### 2.1 设计原则

- **覆盖经典叙事反转类型**：6 个值覆盖主流叙事理论（身份揭露 / 背叛 / 命运反转 / 世界规则 / 牺牲 / 真相揭示）
- **可扩展**：留 `__init__.py` 暴露的常量，1B 实施时如需新增，添加新成员即可
- **不与 PlotPilot 现有 `RevealedClueItem.category` 重复**：Clue 类别与 Twist 类别语义不同

### 2.2 完整类型定义

```python
from enum import Enum


class TwistType(str, Enum):
    """Twist 的语义分类（spec 子文档 §2 锁定 6 类）"""
    IDENTITY_REVEAL = "identity_reveal"          # 身份揭露（卧底/双面人/真身）
    BETRAYAL = "betrayal"                        # 背叛（盟友反目/被信任者欺骗）
    FORTUNE_REVERSAL = "fortune_reversal"        # 命运反转（弱势翻盘/强者陨落）
    WORLD_RULE_REVEAL = "world_rule_reveal"      # 世界规则揭示（魔法体系/科技真相）
    SACRIFICE = "sacrifice"                      # 牺牲（角色以死亡/失去为代价）
    TRUTH_REVEALED = "truth_revealed"            # 真相揭示（核心谜底揭开）
```

### 2.3 语义说明

| 值 | 含义 | 典型 SF_LOG 触发 |
|---|---|---|
| `IDENTITY_REVEAL` | 角色身份/真实身份揭露 | `twist_reveal` + 关联到 `CHARACTER_*` 类型 |
| `BETRAYAL` | 信任关系破裂 | `twist_reveal` + 关联到 `expectation`（违反读者预期） |
| `FORTUNE_REVERSAL` | 力量对比/地位反转 | `twist_reveal` + 关联到 `conflict`（冲突双方换位） |
| `WORLD_RULE_REVEAL` | 设定/魔法体系真相 | `twist_reveal` + 关联到 `reveal` |
| `SACRIFICE` | 角色牺牲 | `twist_reveal` + 关联到 `character_physical_change` (death) |
| `TRUTH_REVEALED` | 核心谜底揭开 | `twist_reveal` + 关联到 `mystery` |

### 2.4 1A 范围

1A 定义 6 个枚举值 + 单元测试覆盖。**CascadeService 中按 `TwistType` 分发的逻辑在 1B**（spec §4.2 暂未要求按类型分发，1B 视情况实施）。

### 2.5 1B/1C 消费

- 1B `CascadeService` 可选：按 `TwistType` 决定是否触发某些 expectation 状态变更
- 1D 前端 `RegistryList.vue`：作为 Twist 列表的 filter 选项

---

## 3. Clue 字段（domain/storyos/entities/mystery.py）

### 3.1 ⚠️ 与 PlotPilot 现有 `RevealedClueItem` 的关系

**重要背景**：PlotPilot **已经存在** `RevealedClueItem` 类（在 `application/engine/services/memory_engine.py:70`）：

```python
class RevealedClueItem(BaseModel):
    clue_id: str
    content: str                                # 线索内容
    revealed_at_chapter: int                    # 揭露章节
    category: str = "truth"                     # truth/relationship/identity/ability/other
    is_still_valid: bool = True                 # 是否被推翻
```

**设计决策（子 spec 锁定 D 方案）**：

| 角色 | 真相源 | 投影 |
|---|---|---|
| **Clue**（domain/storyos） | ✅ 单一真相源：客观存在的线索 | ❌ |
| **RevealedClueItem**（memory_engine） | ❌ | ✅ 由 `MysteryService` 在 Clue 状态变更时投影生成 |

**理由**：
1. StoryOS 是新的 narrative state 基础设施（spec §1.1），应作为单一真相源
2. `RevealedClueItem` 是 per-chapter 揭露记录（事件视角），与 Clue（实体视角）语义不同
3. 避免双写漂移：Clue 状态变更时自动投影到 RevealedClueItem
4. bounded context 隔离：memory_engine 继续独立工作，1A 不破坏现有依赖

### 3.2 Clue 完整类型定义

```python
from dataclasses import dataclass, field
from domain.shared.base_entity import BaseEntity
from domain.storyos.contracts import AssetStatus


class ClueCategory(str, Enum):
    """Clue 的语义分类（与 RevealedClueItem.category 对齐）"""
    TRUTH = "truth"                    # 真相
    RELATIONSHIP = "relationship"      # 关系变化
    IDENTITY = "identity"              # 身份暴露
    ABILITY = "ability"                # 能力揭示
    OTHER = "other"                    # 其他


@dataclass(frozen=True)
class Clue:
    """Mystery 实体的组成成分（spec 子文档 §3 锁定）"""
    id: str
    mystery_id: str
    description: str
    source_chapter: int                           # 线索被埋下的章节（不是揭露章节）
    source_location: str                          # 线索出现的位置/场景/事件
    category: ClueCategory = ClueCategory.TRUTH   # 与 RevealedClueItem.category 对齐
    status: AssetStatus = AssetStatus.PLANTED     # PLANTED/REVEALED/DEAD
    discovered_in_chapter: int | None = None      # 被读者/角色发现的章节（None=未发现）
    invalidated_in_chapter: int | None = None     # 被推翻/证伪的章节（None=仍有效）

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
        """标记为已发现，返回新对象"""
        if self.status != AssetStatus.PLANTED:
            raise ValueError(f"Cannot discover clue in status {self.status.value}")
        if chapter < self.source_chapter:
            raise ValueError(f"discover chapter {chapter} < source_chapter {self.source_chapter}")
        return replace(
            self,
            status=AssetStatus.REVEALED,
            discovered_in_chapter=chapter,
        )

    def invalidate(self, chapter: int) -> "Clue":
        """标记为被推翻/证伪，返回新对象"""
        if self.status not in (AssetStatus.PLANTED, AssetStatus.REVEALED):
            raise ValueError(f"Cannot invalidate clue in status {self.status.value}")
        return replace(
            self,
            status=AssetStatus.DEAD,
            invalidated_in_chapter=chapter,
        )

    def to_revealed_clue_item(self) -> "RevealedClueItem":
        """投影到 RevealedClueItem（1B MysteryService 调用）"""
        from application.engine.services.memory_engine import RevealedClueItem
        return RevealedClueItem(
            clue_id=self.id,
            content=self.description,
            revealed_at_chapter=self.discovered_in_chapter or self.source_chapter,
            category=self.category.value,
            is_still_valid=self.status != AssetStatus.DEAD,
        )
```

### 3.3 字段约束

| 字段 | 约束 | 验证 |
|---|---|---|
| `id` | 业务 ID 字符串 | 调用方负责 |
| `mystery_id` | 必填，关联到 Mystery.id | 调用方负责 |
| `description` | 非空 | `__post_init__` |
| `source_chapter` | `>= 1` | `__post_init__` |
| `source_location` | 非空 | `__post_init__` |
| `category` | 枚举值，默认 `TRUTH` | Pydantic / Enum |
| `status` | 枚举值，默认 `PLANTED` | `__post_init__` 校验必填 |
| `discovered_in_chapter` | `>= source_chapter` | `__post_init__` |
| `invalidated_in_chapter` | `>= source_chapter` | `__post_init__` |

### 3.4 状态转换图

```
PLANTED ──discover()──→ REVEALED ──invalidate()──→ DEAD
   │                       │
   └──invalidate()──────────┘
```

### 3.5 与 `RevealedClueItem` 字段对应

| Clue（domain/storyos） | RevealedClueItem（memory_engine） | 关系 |
|---|---|---|
| `id` | `clue_id` | 同一 ID |
| `description` | `content` | 内容相同（命名差异） |
| `discovered_in_chapter` | `revealed_at_chapter` | 都是揭露章节 |
| `category.value` | `category` | 同一枚举字符串 |
| `status != DEAD` | `is_still_valid` | 推导 |
| `source_chapter` | — | RevealedClueItem 无此字段（Clue 独有） |
| `source_location` | — | RevealedClueItem 无此字段（Clue 独有） |
| `invalidated_in_chapter` | — | 通过 `is_still_valid=False` 间接表示 |

### 3.6 1A 范围

1A 定义 `Clue` + `ClueCategory` + 状态转换方法 + 单元测试。**`to_revealed_clue_item()` 方法导入 memory_engine 违反 DDD 分层规则（domain 不应依赖 application）**，需调整为：

```python
# 1A 范围：只定义 Clue，不实现 to_revealed_clue_item
# 1B 在 application/storyos/services/clue_projection_service.py 实现投影
```

**修正**：1A 不实现 `to_revealed_clue_item()`。1B 在 `MysteryService` 注入 `RevealedClueItem` 的工厂方法。

### 3.7 1B 实施

1B 在 `application/storyos/services/mystery_service.py` 中：
- 当 `Clue.status` 从 PLANTED → REVEALED 转换时，调用 `memory_engine.append_revealed_clue()` 投影
- 当 `Clue.status` → DEAD 时，调用 `memory_engine.invalidate_revealed_clue(clue_id)`

---

## 4. 实施优先级

| 阶段 | 内容 | 任务编号（1A） |
|---|---|---|
| 1A 立即实施 | `SFLogRecord` + `SFLogParam` + 5 字段 | B1 |
| 1A 立即实施 | `TwistType` 6 个枚举值 | C3 |
| 1A 立即实施 | `Clue` + `ClueCategory` + 状态转换 | C2 |
| 1B 实施 | `to_revealed_clue_item` 投影 | MysteryService |
| 1B 实施 | Clue 状态变更时同步更新 RevealedClueItem | MysteryService |
| 1D 实施 | 前端 `RegistryList` 的 Clue filter by category | RegistryList.vue |

---

## 5. 与主 spec 的差异

本子 spec **不修改**主 spec 的设计，仅**填补字段空白**。差异点：

| 项 | 主 spec 状态 | 本子 spec 锁定 |
|---|---|---|
| SFLogRecord 字段 | §3.2 类型表跳过 | 6 字段（log_type/params/raw/chapter_id/char_position/asset_id） |
| SFLogParam 字段 | 未定义 | 2 字段（key/value） |
| TwistType 成员 | 未定义 | 6 个值（IDENTITY_REVEAL/BETRAYAL/FORTUNE_REVERSAL/WORLD_RULE_REVEAL/SACRIFICE/TRUTH_REVEALED） |
| Clue 字段 | 未定义 | 9 字段（含 ClueCategory 枚举） |
| Clue vs RevealedClueItem | 未提及 | Clue 是真相源，RevealedClueItem 是投影 |

---

## 6. 未决问题（Phase 2 决定）

1. **TwistType 是否要更细分？**（如 BETRAYAL 拆为 `BETRAYAL_BY_ALLY` / `BETRAYAL_BY_LOVED`）— 1A 留 6 个值，1B 视需要扩展
2. **Clue 能否关联多个 Mystery？** 当前 1A 强制 1-1（`mystery_id: str`）。如需 M-N，需改 `mystery_ids: tuple[str, ...]`
3. **RevealedClueItem 是否要 deprecate？** 1A 暂保留，1B 投影机制成熟后 Phase 2 决定

---

## 7. 设计参考

- **主 spec**: [`./2026-07-02-storyos-integration-design.md`](./2026-07-02-storyos-integration-design.md) §3.1, §3.2, §4.2, 附录 A
- **现有 RevealedClueItem**: `application/engine/services/memory_engine.py:70-84`
- **现有 ImportanceLevel**: `domain/novel/value_objects/foreshadowing.py:13-18`
- **1A Foundation 实施计划**: [`../plans/2026-07-02-storyos-phase-1a-foundation.md`](../plans/2026-07-02-storyos-phase-1a-foundation.md)
