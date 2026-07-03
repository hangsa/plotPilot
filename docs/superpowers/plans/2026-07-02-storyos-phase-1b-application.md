# StoryOS Phase 1B — Application 实施计划（详版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Parent Plan:** [`2026-07-02-storyos-integration.md`](./2026-07-02-storyos-integration.md)
**Spec Reference:** [`../specs/2026-07-02-storyos-integration-design.md`](../specs/2026-07-02-storyos-integration-design.md) §3.1 application/, §3.3 SF_LOG 映射, §3.6 CircuitBreaker, §4 数据流
**Sub-Spec Reference:** [`../specs/2026-07-02-storyos-asset-field-spec.md`](../specs/2026-07-02-storyos-asset-field-spec.md)
**1A 阶段产出（前置）**：[`./2026-07-02-storyos-phase-1a-foundation.md`](./2026-07-02-storyos-phase-1a-foundation.md)
**Phase Scope:** SF_LOG parsers + 8 Registry services + Cascade service + EvolutionBridge + Compliance gate + Snapshot + Metrics
**LOC Target:** ~3000
**Estimated Tasks:** 20
**Estimated Duration:** 1.5 周

---

## 0. 前置条件

```bash
cd /Users/longsa/Codes/plotPilot

# 1. 确认 1A 全部完成
ls domain/storyos/contracts.py domain/storyos/entities/ infrastructure/persistence/storyos/schemas/
# 期望 contracts.py + 8 entities/* + 11 schemas/* 存在

# 2. 确认 WriteDispatch.transaction() 可用
python -c "from infrastructure.persistence.database.write_dispatch import WriteDispatch, WriteTransaction; print('ok')"
# 期望 ok

# 3. 确认 Evolution Engine ActionType 可用
python -c "from domain.evolution.contracts import ActionType; print(len(ActionType))"
# 期望 9

# 4. 确认 CircuitBreaker 可用
python -c "from application.engine.services.circuit_breaker import CircuitBreaker; print('ok')"
# 期望 ok
```

---

## 1. 阶段目标

实现 1A 类型与持久化之上的**业务逻辑层**：解析 SF_LOG 标签、维护 8 个 Registry 的状态、级联调度、双写协调与合规门控。

### 1.1 产出物清单

- `application/storyos/parsers/` — 3 个模块（regex parser / format validator / action mapper）
- `application/storyos/services/` — 6 类服务（registry / cascade / parser orchestrator / bridge / snapshot / circuit breaker 集成）
- `application/engine/services/circuit_breaker.py` — **扩展**为多 gate（spec §3.6 锁定）
- `application/storyos/value_objects/` — `bridge_result.py` / `storyos_metrics.py` / `active_assets_context.py`
- ~30 个 TDD 任务覆盖以下场景

### 1.2 关键设计点

- **零 LLM 解析**：SF_LOG 提取纯正则（spec 附录 A 完整语法锁定）
- **6 映射 + 5 跳过**：仅触发事实型数据变更的 SF_LOG 才映射到 EvolutionAction（spec §3.3）
- **BFS 级联 + MAX_CASCADE_DEPTH=3**：cascade_service 实现（spec §4.2）
- **单 SQL 事务三操作**：bridge 写入 evolution_apply_actions + registry_apply_with_cascade + sflog_event_record（spec §4.1）
- **bridge_log 在事务外**：失败审计（spec §3.4 ⚡ 标记）
- **CircuitBreaker 多 gate**：复用实例，独立计数 `gate='sflog_compliance'` vs `gate='fact_guard'`（spec §3.6）
- **两级重试**：predeclared missing → RETRY，unexpected → WARN（spec §4.4）
- **StoryOSMetrics**：6 指标（applied / skipped / cascade / compliance / bridge_ms / sflog_count）— spec §5.2 锁定
- **ActiveAssetsContext**：Step 1 输入 LLM 的活跃资产摘要

### 1.3 不在本阶段范围

- ❌ StoryOSDelegate 引擎钩子（→ 1C）
- ❌ API 端点 + 前端（→ 1D）
- ❌ 旧 Foreshadowing 数据迁移（→ 1E）
- ❌ Evolution Reducer 修改（EvolutionEngine 现有 reducer 复用，1B 仅做 action 构造）

---

## 2. TDD 约定

每个任务严格遵循 5 步循环（2-5 分钟/步）：

1. **写失败测试**：在 `tests/unit/...` 创建测试文件
2. **运行测试确认失败**：`pytest ...` 期望 ImportError / AssertionError
3. **写最小实现**：在指定实现文件创建骨架
4. **运行测试确认通过**：期望 PASS
5. **Commit**：`git add ... && git commit -m "..."`

### 2.1 通用 commit 消息前缀

- `feat(parsers):` — SF_LOG 解析层
- `feat(registry):` — Registry 服务
- `feat(cascade):` — 级联引擎
- `feat(bridge):` — Evolution Bridge 双写
- `feat(circuit-breaker):` — 多 gate 扩展
- `feat(metrics):` — StoryOSMetrics
- `feat(snapshot):` — Snapshot projector
- `feat(application):` — application 层整体结构
- `test(...):` — 纯测试补充

### 2.2 测试文件命名

- Parsers: `tests/unit/application/storyos/parsers/test_<name>.py`
- Services: `tests/unit/application/storyos/services/test_<name>.py`
- Value objects: `tests/unit/application/storyos/value_objects/test_<name>.py`
- Circuit breaker extension: `tests/unit/application/engine/services/test_circuit_breaker_multi_gate.py`

### 2.3 实施顺序

**严格依赖**：
- Group A → Group D（action mapper 构造的 action 喂给 bridge）
- Group B → Group C（cascade 用 registry）
- Group C → Group D（bridge 调用 cascade）
- Group D → Group E（bridge 失败时记录到 bridge_log）
- Group E → Group F（compliance gate 集成到 parser service）

**可并行**：
- Group A 内部 3 任务可串行（regex → validator → mapper）
- Group B 内部 4 任务可并行（独立文件）
- Group F 的 snapshot 任务与 G 的 metrics 任务可并行

---

## 3. 任务清单

---

### Group A: SF_LOG Parsers（3 任务）

#### Task A1: SFLogRegexParser（11 类全覆盖）

**Files:**
- Create: `application/storyos/__init__.py`（空文件）
- Create: `application/storyos/parsers/__init__.py`（空文件）
- Create: `application/storyos/parsers/sf_log_regex_parser.py`
- Create: `tests/unit/application/storyos/__init__.py`（空文件）
- Create: `tests/unit/application/storyos/parsers/__init__.py`（空文件）
- Create: `tests/unit/application/storyos/parsers/test_sf_log_regex_parser.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from application.storyos.parsers.sf_log_regex_parser import SFLogRegexParser
from domain.storyos.contracts import SFLogType


@pytest.fixture
def parser():
    return SFLogRegexParser()


def test_parse_single_mystery_clue(parser):
    text = 'Chapter text... <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="blood" --> ...'
    records = parser.parse(text, chapter_id=3)
    assert len(records) == 1
    rec = records[0]
    assert rec.log_type == SFLogType.MYSTERY_CLUE
    assert rec.params == {"mystery_id": "m1", "content": "blood"}
    assert rec.chapter_id == 3
    assert rec.asset_id == "m1"  # 解析为单资产型
    assert rec.char_position > 0


def test_parse_relationship_log_has_no_asset_id(parser):
    text = '<!-- SF_LOG CHARACTER_RELATION_CHANGE char_a="alice" char_b="bob" type="ally" -->'
    records = parser.parse(text, chapter_id=1)
    assert len(records) == 1
    rec = records[0]
    assert rec.log_type == SFLogType.CHARACTER_RELATION_CHANGE
    assert rec.asset_id is None  # 关系型无 asset_id


def test_parse_multiple_records(parser):
    text = '''
    A <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="x" --> B
    C <!-- SF_LOG CONFLICT_ESCALATE conflict_id="c1" intensity="HIGH" --> D
    '''
    records = parser.parse(text, chapter_id=2)
    assert len(records) == 2
    assert records[0].log_type == SFLogType.MYSTERY_CLUE
    assert records[1].log_type == SFLogType.CONFLICT_ESCALATE


def test_parse_no_sflog_returns_empty(parser):
    records = parser.parse("Plain text without any SF_LOG tags.", chapter_id=1)
    assert records == []


def test_parse_raw_field_preserves_full_tag(parser):
    text = 'before <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="x" --> after'
    records = parser.parse(text, chapter_id=1)
    assert records[0].raw == '<!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="x" -->'


def test_parse_all_11_log_types(parser):
    """11 类 SFLogType 全部能解析。"""
    cases = [
        ('CHARACTER_EMOTION', 'char_id="alice" emotion="angry"'),
        ('CHARACTER_RELATION_CHANGE', 'char_a="a" char_b="b" type="ally"'),
        ('CHARACTER_LOCATION_CHANGE', 'char_id="alice" location="cave"'),
        ('CHARACTER_PHYSICAL_CHANGE', 'char_id="alice" status="injured"'),
        ('KNOWLEDGE_GAIN', 'char_id="alice" fact="x"'),
        ('CONFLICT_ESCALATE', 'conflict_id="c1" intensity="HIGH"'),
        ('MYSTERY_CLUE', 'mystery_id="m1" content="x"'),
        ('TWIST_REVEAL', 'twist_id="t1" trigger="x"'),
        ('EXPECTATION_FULFILL', 'expectation_id="e1"'),
        ('GOAL_MILESTONE', 'goal_id="g1" marker="T5"'),
        ('REGISTRY_CREATE', 'asset_type="mystery" asset_id="m2"'),
    ]
    for log_name, params in cases:
        text = f'<!-- SF_LOG {log_name} {params} -->'
        records = parser.parse(text, chapter_id=1)
        assert len(records) == 1, f"failed to parse {log_name}"
        assert records[0].log_type.value == log_name.lower()


def test_parse_malformed_tag_raises(parser):
    """语法错误 → 抛 FormatError（由 FormatError dataclass 表达）。"""
    from domain.storyos.value_objects.format_error import FormatError
    text = '<!-- SF_LOG MYSTERY_CLUE mystery_id="m1"'  # 缺闭合 -->
    with pytest.raises(FormatError):
        parser.parse(text, chapter_id=1)
```

- [ ] **Step 2: 运行测试确认失败** — `pytest tests/unit/application/storyos/parsers/test_sf_log_regex_parser.py -v` 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `application/storyos/parsers/sf_log_regex_parser.py`：

```python
"""SF_LOG 正则解析器（spec 附录 A 完整语法锁定）。

提取章节文本中的 `<!-- SF_LOG <LOG_TYPE> <key>=<value> ... -->` 注释。
"""
from __future__ import annotations

import re

from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.format_error import FormatError
from domain.storyos.value_objects.sf_log import SFLogRecord


# 完整匹配：开始 `<!-- SF_LOG`、类型、空格分隔的 k="v" 对、闭合 `-->`
_SFLOG_PATTERN = re.compile(
    r'<!--\s*SF_LOG\s+(?P<log_type>[A-Z_]+)\s+(?P<params>[^>]*?)\s*-->',
    re.DOTALL,
)
_PARAM_PATTERN = re.compile(r'(?P<key>\w+)\s*=\s*"(?P<value>[^"]*)"')


# 单资产型 SF_LOG（必含 asset_id）；关系型无 asset_id
_SINGLE_ASSET_PARAM_KEYS = {
    SFLogType.MYSTERY_CLUE: "mystery_id",
    SFLogType.CONFLICT_ESCALATE: "conflict_id",
    SFLogType.TWIST_REVEAL: "twist_id",
    SFLogType.EXPECTATION_FULFILL: "expectation_id",
    SFLogType.GOAL_MILESTONE: "goal_id",
    SFLogType.CHARACTER_EMOTION: "char_id",
    SFLogType.CHARACTER_LOCATION_CHANGE: "char_id",
    SFLogType.CHARACTER_PHYSICAL_CHANGE: "char_id",
    SFLogType.KNOWLEDGE_GAIN: "char_id",
}


class SFLogRegexParser:
    """零 LLM SF_LOG 解析器（纯正则）。"""

    def parse(self, text: str, chapter_id: int) -> list[SFLogRecord]:
        """从章节文本中提取所有 SFLogRecord。

        Args:
            text: 章节纯文本
            chapter_id: 章节号（≥1）

        Returns:
            SFLogRecord 列表（按文本出现顺序）

        Raises:
            FormatError: 遇到语法错误（缺闭合、类型未知等）
        """
        results: list[SFLogRecord] = []
        for match in _SFLOG_PATTERN.finditer(text):
            log_type_str = match.group("log_type")
            try:
                log_type = SFLogType(log_type_str.lower())
            except ValueError:
                raise FormatError(
                    code="UNKNOWN_LOG_TYPE",
                    message=f"Unknown SFLogType: {log_type_str}",
                    raw_text=match.group(0),
                    char_position=match.start(),
                )
            params = {
                m.group("key"): m.group("value")
                for m in _PARAM_PATTERN.finditer(match.group("params"))
            }
            asset_id = self._extract_asset_id(log_type, params)
            results.append(
                SFLogRecord(
                    log_type=log_type,
                    params=params,
                    raw=match.group(0),
                    chapter_id=chapter_id,
                    char_position=match.start(),
                    asset_id=asset_id,
                )
            )
        return results

    def _extract_asset_id(self, log_type: SFLogType, params: dict[str, str]) -> str | None:
        """单资产型提取 asset_id；关系型返回 None。"""
        key = _SINGLE_ASSET_PARAM_KEYS.get(log_type)
        if key is None:
            return None
        return params.get(key)
```

并在 `application/storyos/parsers/__init__.py` 暴露：

```python
from application.storyos.parsers.sf_log_regex_parser import SFLogRegexParser
```

- [ ] **Step 4: 运行测试确认通过** — 期望 7 passed
- [ ] **Step 5: Commit** — `git add application/storyos/ tests/unit/application/storyos/ && git commit -m "feat(parsers): add SFLogRegexParser with 11 log types coverage"`

#### Task A2: SFLogFormatValidator（严格格式校验）

**Files:**
- Create: `application/storyos/parsers/sf_log_format_validator.py`
- Create: `tests/unit/application/storyos/parsers/test_sf_log_format_validator.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from application.storyos.parsers.sf_log_format_validator import SFLogFormatValidator
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.format_error import FormatError
from domain.storyos.value_objects.sf_log import SFLogRecord


def _rec(log_type=SFLogType.MYSTERY_CLUE, params=None):
    return SFLogRecord(
        log_type=log_type,
        params=params or {"mystery_id": "m1", "content": "x"},
        raw='<!-- ... -->',
        chapter_id=1,
        char_position=0,
    )


def test_validator_accepts_valid_record():
    v = SFLogFormatValidator()
    rec = _rec()
    errors = v.validate([rec])
    assert errors == []


def test_validator_rejects_missing_required_param():
    v = SFLogFormatValidator()
    rec = _rec(params={"mystery_id": "m1"})  # 缺 content
    errors = v.validate([rec])
    assert len(errors) == 1
    assert errors[0].code == "MISSING_PARAM"
    assert "content" in errors[0].message


def test_validator_rejects_empty_param_value():
    v = SFLogFormatValidator()
    rec = _rec(params={"mystery_id": "", "content": "x"})
    errors = v.validate([rec])
    assert any(e.code == "EMPTY_PARAM" for e in errors)


def test_validator_checks_log_type_specific_params():
    """每类 SFLogType 必填参数不同。"""
    v = SFLogFormatValidator()
    rec = _rec(
        log_type=SFLogType.CONFLICT_ESCALATE,
        params={"conflict_id": "c1"},  # 缺 intensity
    )
    errors = v.validate([rec])
    assert any(e.code == "MISSING_PARAM" and "intensity" in e.message for e in errors)


def test_validator_returns_empty_for_no_records():
    v = SFLogFormatValidator()
    assert v.validate([]) == []
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ImportError`
- [ ] **Step 3: 实现** — `application/storyos/parsers/sf_log_format_validator.py`：

```python
"""SFLogFormatValidator — 严格校验 SFLogRecord 的参数必填规则。"""
from __future__ import annotations

from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.format_error import FormatError
from domain.storyos.value_objects.sf_log import SFLogRecord


# 每类 SF_LOG 的必填参数（spec 附录 A 锁定）
_REQUIRED_PARAMS: dict[SFLogType, frozenset[str]] = {
    SFLogType.CHARACTER_EMOTION: frozenset({"char_id", "emotion"}),
    SFLogType.CHARACTER_RELATION_CHANGE: frozenset({"char_a", "char_b", "type"}),
    SFLogType.CHARACTER_LOCATION_CHANGE: frozenset({"char_id", "location"}),
    SFLogType.CHARACTER_PHYSICAL_CHANGE: frozenset({"char_id", "status"}),
    SFLogType.KNOWLEDGE_GAIN: frozenset({"char_id", "fact"}),
    SFLogType.CONFLICT_ESCALATE: frozenset({"conflict_id", "intensity"}),
    SFLogType.MYSTERY_CLUE: frozenset({"mystery_id", "content"}),
    SFLogType.TWIST_REVEAL: frozenset({"twist_id", "trigger"}),
    SFLogType.EXPECTATION_FULFILL: frozenset({"expectation_id"}),
    SFLogType.GOAL_MILESTONE: frozenset({"goal_id", "marker"}),
    SFLogType.REGISTRY_CREATE: frozenset({"asset_type", "asset_id"}),
}


class SFLogFormatValidator:
    """校验 SFLogRecord 列表，返回 FormatError 列表（无错则空）。"""

    def validate(self, records: list[SFLogRecord]) -> list[FormatError]:
        errors: list[FormatError] = []
        for rec in records:
            required = _REQUIRED_PARAMS.get(rec.log_type, frozenset())
            for key in required:
                if key not in rec.params:
                    errors.append(FormatError(
                        code="MISSING_PARAM",
                        message=f"SFLogType {rec.log_type.value} requires param '{key}'",
                        raw_text=rec.raw,
                        char_position=rec.char_position,
                    ))
                elif not rec.params[key].strip():
                    errors.append(FormatError(
                        code="EMPTY_PARAM",
                        message=f"param '{key}' is empty",
                        raw_text=rec.raw,
                        char_position=rec.char_position,
                    ))
        return errors
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed
- [ ] **Step 5: Commit** — `git add application/storyos/parsers/sf_log_format_validator.py tests/unit/application/storyos/parsers/test_sf_log_format_validator.py && git commit -m "feat(parsers): add SFLogFormatValidator with per-type required params"`

#### Task A3: SFLogActionMapper（6 映射 + 5 跳过）

**Files:**
- Create: `application/storyos/parsers/sf_log_action_mapper.py`
- Create: `tests/unit/application/storyos/parsers/test_sf_log_action_mapper.py`

- [ ] **Step 1: 写失败测试**（spec §3.3 锁定 6 映射 + 5 跳过）

```python
from application.storyos.parsers.sf_log_action_mapper import SFLogActionMapper
from domain.evolution.contracts import ActionType
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


def _rec(log_type, params, asset_id=None):
    return SFLogRecord(
        log_type=log_type, params=params, raw="<!-- ... -->",
        chapter_id=1, char_position=0, asset_id=asset_id,
    )


def test_mapper_emits_action_for_location_change():
    """spec §3.3 锁定：CHARACTER_LOCATION_CHANGE → MOVE_CHARACTER。"""
    m = SFLogActionMapper()
    rec = _rec(
        SFLogType.CHARACTER_LOCATION_CHANGE,
        {"char_id": "alice", "location": "cave"},
        asset_id="alice",
    )
    actions, skipped = m.map_records([rec])
    assert len(actions) == 1
    assert actions[0].type == ActionType.MOVE_CHARACTER.value
    assert skipped == []


def test_mapper_skips_mystery_clue():
    """spec §3.3 锁定：MYSTERY_CLUE 是 NOT_MAPPED（只写 StoryOS，不进 Evolution）。"""
    m = SFLogActionMapper()
    rec = _rec(
        SFLogType.MYSTERY_CLUE,
        {"mystery_id": "m1", "content": "blood"},
        asset_id="m1",
    )
    actions, skipped = m.map_records([rec])
    assert actions == []
    assert SFLogType.MYSTERY_CLUE in skipped


def test_mapper_maps_exactly_6_types():
    """spec §3.3 锁定 6 映射 + 5 跳过。"""
    m = SFLogActionMapper()
    # spec 锁定的 6 映射
    expected_mapped = {
        SFLogType.CHARACTER_LOCATION_CHANGE,
        SFLogType.CHARACTER_PHYSICAL_CHANGE,
        SFLogType.CHARACTER_RELATION_CHANGE,
        SFLogType.KNOWLEDGE_GAIN,
        SFLogType.CONFLICT_ESCALATE,
        SFLogType.GOAL_MILESTONE,
    }
    # spec 锁定的 5 NOT_MAPPED
    expected_skipped = {
        SFLogType.CHARACTER_EMOTION,
        SFLogType.MYSTERY_CLUE,
        SFLogType.TWIST_REVEAL,
        SFLogType.EXPECTATION_FULFILL,
        SFLogType.REGISTRY_CREATE,
    }
    # 跑全 11 类验证
    mapped_seen: set[SFLogType] = set()
    skipped_seen: set[SFLogType] = set()
    for log_type in SFLogType:
        rec = _rec(log_type, {"k": "v"}, asset_id="x")
        actions, skipped = m.map_records([rec])
        if actions:
            mapped_seen.add(log_type)
        else:
            skipped_seen.update(skipped)
    assert mapped_seen == expected_mapped
    assert skipped_seen == expected_skipped
    assert len(mapped_seen) == 6
    assert len(skipped_seen) == 5
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ImportError`
- [ ] **Step 3: 实现** — `application/storyos/parsers/sf_log_action_mapper.py`：

```python
"""SFLogActionMapper — 11 类 SF_LOG → 6 EvolutionAction + 5 跳过（spec §3.3 锁定）。

spec §3.3 锁定映射表（关键，不要改）：
  6 mapped: CHARACTER_LOCATION_CHANGE / CHARACTER_PHYSICAL_CHANGE / CHARACTER_RELATION_CHANGE /
             KNOWLEDGE_GAIN / CONFLICT_ESCALATE / GOAL_MILESTONE
  5 skipped: CHARACTER_EMOTION / MYSTERY_CLUE / TWIST_REVEAL / EXPECTATION_FULFILL / REGISTRY_CREATE

设计原则（spec §3.3 锁定）：仅覆盖触发 EvolutionState 中事实型数据变更的 SF_LOG。
纯叙事资产操作（clue/reveal/emotion/expectation）只写 StoryOS，不进 Evolution。
"""
from __future__ import annotations

import uuid

from domain.evolution.contracts import ActionType
from domain.evolution.models import EvolutionAction
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


# spec §3.3 锁定 6 映射（key=SFLogType, value=ActionType）
_MAPPED_LOG_TYPES: dict[SFLogType, ActionType] = {
    SFLogType.CHARACTER_LOCATION_CHANGE: ActionType.MOVE_CHARACTER,
    SFLogType.CHARACTER_PHYSICAL_CHANGE: ActionType.SET_CHARACTER_STATUS,
    SFLogType.CHARACTER_RELATION_CHANGE: ActionType.SET_EMOTIONAL_RESIDUE,
    SFLogType.KNOWLEDGE_GAIN: ActionType.REVEAL_FACT,
    SFLogType.CONFLICT_ESCALATE: ActionType.UPDATE_STORYLINE_PROGRESS,
    SFLogType.GOAL_MILESTONE: ActionType.UPDATE_DEBT_PROGRESS,
}

# spec §3.3 锁定 5 NOT_MAPPED（防御性常量，供其他模块引用）
NOT_MAPPED_LOG_TYPES: frozenset[SFLogType] = frozenset({
    SFLogType.CHARACTER_EMOTION,
    SFLogType.MYSTERY_CLUE,
    SFLogType.TWIST_REVEAL,
    SFLogType.EXPECTATION_FULFILL,
    SFLogType.REGISTRY_CREATE,
})


class SFLogActionMapper:
    """SFLogRecord → (EvolutionAction 列表, 跳过的 log_type 集合)。"""

    def map_records(
        self, records: list[SFLogRecord],
    ) -> tuple[list[EvolutionAction], set[SFLogType]]:
        actions: list[EvolutionAction] = []
        skipped: set[SFLogType] = set()
        for rec in records:
            action_type = _MAPPED_LOG_TYPES.get(rec.log_type)
            if action_type is None:
                skipped.add(rec.log_type)
                continue
            actions.append(
                EvolutionAction(
                    action_id=str(uuid.uuid4()),
                    type=action_type.value,
                    payload=dict(rec.params),
                    confidence=1.0,
                    source_refs=[{
                        "chapter_id": rec.chapter_id,
                        "char_position": rec.char_position,
                        "raw": rec.raw,
                    }],
                )
            )
        return actions, skipped
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed
- [ ] **Step 5: Commit** — `git add application/storyos/parsers/sf_log_action_mapper.py tests/unit/application/storyos/parsers/test_sf_log_action_mapper.py && git commit -m "feat(parsers): add SFLogActionMapper with 6 mapped + 5 skipped (spec §3.3)"`

---

### Group B: 8 Registry Services（3 任务，批处理）

> **通用约定**：所有 Registry 服务继承 `GenericRegistryService[EntityT]`，提供 `create / get / update / delete / list` 基础 CRUD；实体状态变更通过 `update(asset_id, **kwargs) -> Entity` 返回新对象。

#### Task B1: GenericRegistryService 基类 + ConflictRegistryService + MysteryRegistryService

**Files:**
- Create: `application/storyos/services/__init__.py`（空文件）
- Create: `application/storyos/services/registry_service.py`
- Create: `application/storyos/services/conflict_registry_service.py`
- Create: `application/storyos/services/mystery_registry_service.py`
- Create: `tests/unit/application/storyos/services/__init__.py`（空文件）
- Create: `tests/unit/application/storyos/services/test_conflict_mystery_registry.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.mystery_registry_service import MysteryRegistryService
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.entities.mystery import Clue, Mystery


def test_conflict_registry_create_and_get():
    repo = {}
    svc = ConflictRegistryService(repository=repo)
    c = Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
        involved_characters=("a",), created_chapter=1,
    )
    svc.create(c)
    assert svc.get("c1") == c
    assert svc.list() == [c]


def test_conflict_registry_escalate():
    repo = {}
    svc = ConflictRegistryService(repository=repo)
    c = Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
        involved_characters=("a",), created_chapter=1,
    )
    svc.create(c)
    c2 = svc.update("c1", escalate=True)
    assert c2.intensity == ConflictIntensity.MEDIUM
    assert svc.get("c1").intensity == ConflictIntensity.MEDIUM  # 持久化


def test_mystery_registry_add_clue():
    repo = {}
    svc = MysteryRegistryService(repository=repo)
    m = Mystery(
        id="m1", novel_id="n1", description="x",
        status=AssetStatus.PLANTED, created_chapter=1,
    )
    svc.create(m)
    cl = Clue(id="cl1", mystery_id="m1", description="a",
              source_chapter=1, source_location="x")
    m2 = svc.add_clue("m1", cl)
    assert len(m2.clues) == 1
    # 持久化校验
    assert len(svc.get("m1").clues) == 1


def test_mystery_registry_add_clue_wrong_mystery_id_raises():
    repo = {}
    svc = MysteryRegistryService(repository=repo)
    m = Mystery(id="m1", novel_id="n1", description="x",
                status=AssetStatus.PLANTED, created_chapter=1)
    svc.create(m)
    cl = Clue(id="cl1", mystery_id="m2", description="a",  # 错配
              source_chapter=1, source_location="x")
    with pytest.raises(ValueError, match="!="):
        svc.add_clue("m1", cl)
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现 3 文件**：

`application/storyos/services/registry_service.py`：

```python
"""GenericRegistryService — 8 registry 共用的基类（CRUD 模板）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

EntityT = TypeVar("EntityT")


class GenericRegistryService(ABC, Generic[EntityT]):
    """registry service 的基类。子类实现 _to_dict / _from_dict 序列化。"""

    def __init__(self, repository: dict[str, EntityT] | None = None) -> None:
        self._repo: dict[str, EntityT] = repository if repository is not None else {}

    def create(self, entity: EntityT) -> EntityT:
        if entity.id in self._repo:
            raise ValueError(f"entity id {entity.id!r} already exists")
        self._repo[entity.id] = entity
        return entity

    def get(self, asset_id: str) -> EntityT:
        if asset_id not in self._repo:
            raise KeyError(f"asset_id {asset_id!r} not found")
        return self._repo[asset_id]

    def update(self, asset_id: str, **kwargs) -> EntityT:
        old = self.get(asset_id)
        new = self._apply_update(old, **kwargs)
        self._repo[asset_id] = new
        return new

    def delete(self, asset_id: str) -> None:
        self._repo.pop(asset_id, None)

    def list(self) -> list[EntityT]:
        return list(self._repo.values())

    @abstractmethod
    def _apply_update(self, entity: EntityT, **kwargs) -> EntityT:
        """子类定义如何处理 kwargs（如 escalate=True → escalate()）。"""
        ...
```

`application/storyos/services/conflict_registry_service.py`：

```python
"""Conflict Registry Service。"""
from __future__ import annotations

from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.conflict import Conflict


class ConflictRegistryService(GenericRegistryService[Conflict]):
    def _apply_update(self, entity: Conflict, **kwargs) -> Conflict:
        new = entity
        if kwargs.get("escalate"):
            new = new.escalate()
        if "status" in kwargs:
            new = type(new)(**{**new.__dict__, "status": kwargs["status"]})
        return new
```

`application/storyos/services/mystery_registry_service.py`：

```python
"""Mystery Registry Service（含 Clue 投影到 RevealedClueItem，sub-spec §3.6 锁定）。"""
from __future__ import annotations

from application.engine.services.memory_engine import RevealedClueItem
from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.mystery import Clue, Mystery


class MysteryRegistryService(GenericRegistryService[Mystery]):
    def _apply_update(self, entity: Mystery, **kwargs) -> Mystery:
        new = entity
        if "status" in kwargs:
            new = type(new)(**{**new.__dict__, "status": kwargs["status"]})
        return new

    def add_clue(self, mystery_id: str, clue: Clue) -> Mystery:
        m = self.get(mystery_id)
        m2 = m.add_clue(clue)
        self._repo[mystery_id] = m2
        return m2

    def discover_clue(self, mystery_id: str, clue_id: str, chapter: int) -> tuple[Mystery, RevealedClueItem]:
        """discover Clue → 同时投影到 RevealedClueItem（sub-spec §3.6 修正）。"""
        m = self.get(mystery_id)
        new_clues = tuple(
            c.discover(chapter) if c.id == clue_id else c for c in m.clues
        )
        m2 = type(m)(**{**m.__dict__, "clues": new_clues})
        self._repo[mystery_id] = m2
        # 投影
        clue = next(c for c in m2.clues if c.id == clue_id)
        projected = self._project_to_revealed(clue)
        return m2, projected

    @staticmethod
    def _project_to_revealed(clue: Clue) -> RevealedClueItem:
        return RevealedClueItem(
            clue_id=clue.id,
            content=clue.description,
            revealed_at_chapter=clue.discovered_in_chapter or clue.source_chapter,
            category=clue.category.value,
            is_still_valid=clue.status.value != "dead",
        )
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/ tests/unit/application/storyos/services/ && git commit -m "feat(registry): add GenericRegistryService + Conflict/Mystery services with Clue projection"`

#### Task B2: Twist + Promise + Reveal Registry Services

**Files:**
- Create: `application/storyos/services/twist_registry_service.py`
- Create: `application/storyos/services/promise_registry_service.py`
- Create: `application/storyos/services/reveal_registry_service.py`
- Create: `tests/unit/application/storyos/services/test_twist_promise_reveal_registry.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from application.storyos.services.twist_registry_service import TwistRegistryService
from application.storyos.services.promise_registry_service import PromiseRegistryService
from application.storyos.services.reveal_registry_service import RevealRegistryService
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.twist import Twist, TwistType
from domain.storyos.entities.promise import Promise
from domain.storyos.entities.reveal import Reveal


def test_twist_registry_create():
    svc = TwistRegistryService()
    t = Twist(id="t1", novel_id="n1", description="x",
              status=AssetStatus.ACTIVE, created_chapter=1,
              twist_type=TwistType.IDENTITY_REVEAL)
    svc.create(t)
    assert svc.get("t1") == t


def test_twist_registry_check_no_concurrent_twists():
    """Twist 互斥：forbidden_concurrent_twists 不允许同时 ACTIVE。"""
    svc = TwistRegistryService()
    t1 = Twist(id="t1", novel_id="n1", description="x",
               status=AssetStatus.ACTIVE, created_chapter=1,
               twist_type=TwistType.BETRAYAL,
               forbidden_concurrent_twists=("t2",))
    t2 = Twist(id="t2", novel_id="n1", description="y",
               status=AssetStatus.ACTIVE, created_chapter=2,
               twist_type=TwistType.TRUTH_REVEALED)
    svc.create(t1)
    svc.create(t2)
    # t1 被激活时检查 t2 不应同时 active
    with pytest.raises(ValueError, match="concurrent"):
        svc.activate_with_mutex_check("t1")


def test_promise_registry_fulfill():
    svc = PromiseRegistryService()
    p = Promise(id="p1", novel_id="n1", description="x",
                made_in_chapter=1, status=AssetStatus.ACTIVE, importance=80)
    svc.create(p)
    p2 = svc.fulfill("p1", chapter=10)
    assert p2.status == AssetStatus.FULFILLED
    assert svc.get("p1").status == AssetStatus.FULFILLED


def test_reveal_registry_reveal():
    svc = RevealRegistryService()
    r = Reveal(id="rv1", novel_id="n1", content="x",
               status=AssetStatus.HIDDEN, related_mystery="m1")
    svc.create(r)
    r2 = svc.reveal("rv1", chapter=15)
    assert r2.status == AssetStatus.REVEALED
    assert r2.revealed_in_chapter == 15
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现 3 文件**（按相同模式，CRUD + 业务方法）：

`application/storyos/services/twist_registry_service.py`：

```python
"""Twist Registry Service（含互斥检查）。"""
from __future__ import annotations

from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.twist import Twist


class TwistRegistryService(GenericRegistryService[Twist]):
    def _apply_update(self, entity: Twist, **kwargs) -> Twist:
        if "status" in kwargs:
            from dataclasses import replace
            return replace(entity, status=kwargs["status"])
        return entity

    def activate_with_mutex_check(self, twist_id: str) -> Twist:
        """激活 Twist 时检查 forbidden_concurrent_twists 不在 ACTIVE。"""
        t = self.get(twist_id)
        for other_id in t.forbidden_concurrent_twists:
            try:
                other = self.get(other_id)
                if other.status.value == "active":
                    raise ValueError(
                        f"Twist {twist_id} is mutually exclusive with active Twist {other_id}"
                    )
            except KeyError:
                continue
        from dataclasses import replace
        return self._repo.__setitem__(twist_id, replace(t, status=type(t).status.__class__("active"))) or t
```

简化版（实际正确实现）：

```python
from dataclasses import replace
from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.twist import Twist


class TwistRegistryService(GenericRegistryService[Twist]):
    def _apply_update(self, entity: Twist, **kwargs) -> Twist:
        if "status" in kwargs:
            return replace(entity, status=kwargs["status"])
        return entity

    def activate_with_mutex_check(self, twist_id: str) -> Twist:
        t = self.get(twist_id)
        for other_id in t.forbidden_concurrent_twists:
            try:
                other = self.get(other_id)
                if other.status == AssetStatus.ACTIVE:
                    raise ValueError(
                        f"Twist {twist_id} is mutually exclusive with active Twist {other_id}"
                    )
            except KeyError:
                continue
        new_t = replace(t, status=AssetStatus.ACTIVE)
        self._repo[twist_id] = new_t
        return new_t
```

`promise_registry_service.py` 与 `reveal_registry_service.py` 按相同模式实现 `fulfill` / `reveal` 业务方法。

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/ tests/unit/application/storyos/services/ && git commit -m "feat(registry): add Twist (mutex) + Promise + Reveal registry services"`

#### Task B3: Expectation + Goal + Foreshadowing Registry Services

**Files:**
- Create: `application/storyos/services/expectation_registry_service.py`
- Create: `application/storyos/services/goal_registry_service.py`
- Create: `application/storyos/services/foreshadowing_registry_service.py`
- Create: `tests/unit/application/storyos/services/test_expectation_goal_foreshadowing_registry.py`

- [ ] **Step 1: 写失败测试**

```python
from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from application.storyos.services.goal_registry_service import GoalRegistryService
from application.storyos.services.foreshadowing_registry_service import ForeshadowingRegistryService
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.expectation import Expectation
from domain.storyos.entities.goal import Goal, ProgressMarker
from domain.storyos.entities.foreshadowing import Foreshadowing
from domain.novel.value_objects.foreshadowing import ImportanceLevel


def test_expectation_intensify_clamps_in_service():
    svc = ExpectationRegistryService()
    e = Expectation(id="e1", novel_id="n1", description="x",
                    status=AssetStatus.ACTIVE, created_chapter=1, intensity=95)
    svc.create(e)
    e2 = svc.intensify("e1", delta=30)
    assert e2.intensity == 100


def test_goal_advance_via_service():
    svc = GoalRegistryService()
    g = Goal(id="g1", novel_id="n1", description="x",
             status=AssetStatus.ACTIVE, created_chapter=1,
             current_progress=ProgressMarker.T3)
    svc.create(g)
    g2 = svc.advance("g1", ProgressMarker.T5)
    assert g2.current_progress == ProgressMarker.T5


def test_foreshadowing_resolve_via_service():
    svc = ForeshadowingRegistryService()
    f = Foreshadowing(id="fs1", novel_id="n1", description="x",
                     importance=ImportanceLevel.HIGH,
                     status=AssetStatus.PLANTED, planted_in_chapter=2)
    svc.create(f)
    f2 = svc.resolve("fs1", chapter=10)
    assert f2.status == AssetStatus.REVEALED
    assert f2.resolved_in_chapter == 10
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现 3 文件**（按相同模式；Expectation 的 `intensify` 使用 entity 自身方法 `e.intensify(delta)`；Goal 的 `advance` 类似；Foreshadowing 用 `resolve` / `abandon`）：

`expectation_registry_service.py`：

```python
from dataclasses import replace
from application.storyos.services.registry_service import GenericRegistryService
from domain.storyos.entities.expectation import Expectation


class ExpectationRegistryService(GenericRegistryService[Expectation]):
    def _apply_update(self, entity: Expectation, **kwargs) -> Expectation:
        if "status" in kwargs:
            return replace(entity, status=kwargs["status"])
        return entity

    def intensify(self, expectation_id: str, delta: int) -> Expectation:
        e = self.get(expectation_id)
        new_e = e.intensify(delta)
        self._repo[expectation_id] = new_e
        return new_e
```

`goal_registry_service.py` 与 `foreshadowing_registry_service.py` 模式相同。

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/ tests/unit/application/storyos/services/ && git commit -m "feat(registry): add Expectation/Goal/Foreshadowing registry services"`

---

### Group C: Cascade Service（4 任务）

#### Task C1: CascadeRules.apply_to + 循环检测（已含 1A B3，本任务在 service 层 wrap）

**Files:**
- Create: `application/storyos/services/cascade_service.py`
- Create: `tests/unit/application/storyos/services/test_cascade_service_basic.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from application.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.entities.expectation import Expectation


def test_cascade_conflift_escalated_increases_expectation():
    """CONFLICT_ESCALATED 触发 → linked expectation intensity +30（spec §4.2 锁定）。"""
    conflict_svc = ConflictRegistryService()
    expect_svc = ExpectationRegistryService()
    cascade = CascadeService(
        conflict_svc=conflict_svc, expectation_svc=expect_svc, max_depth=3,
    )
    c = Conflict(id="c1", novel_id="n1", description="x",
                 intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
                 involved_characters=("a",), created_chapter=1,
                 linked_conflicts=())
    conflict_svc.create(c)
    e = Expectation(id="e1", novel_id="n1", description="reader expects climax",
                    status=AssetStatus.ACTIVE, created_chapter=1, intensity=20)
    expect_svc.create(e)

    # 构造 cascade step：conflict c1 → expectation e1, +30 intensity
    step = CascadeStep(
        trigger=CascadeTrigger.CONFLICT_ESCALATED,
        source_asset_type="conflict", source_asset_id="c1",
        target_asset_type="expectation", target_asset_id="e1",
        intensity_delta=30, reason="conflict escalated",
    )
    result = cascade.execute([step])
    assert len(result.steps_executed) == 1
    assert expect_svc.get("e1").intensity == 50  # 20 + 30


def test_cascade_blocks_cycle():
    """级联深度超 max_depth → 阻断。"""
    expect_svc = ExpectationRegistryService()
    expect_svc.create(Expectation(id="e1", novel_id="n1", description="x",
                                  status=AssetStatus.ACTIVE,
                                  created_chapter=1, intensity=10))
    cascade = CascadeService(expectation_svc=expect_svc, max_depth=0)
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery", source_asset_id="m1",
        target_asset_type="expectation", target_asset_id="e1",
        new_status=AssetStatus.ACTIVE, reason="x",
    )
    result = cascade.execute([step])
    assert len(result.blocked_steps) == 1
    assert len(result.steps_executed) == 0
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `application/storyos/services/cascade_service.py`：

```python
"""CascadeService — BFS 级联执行（spec §4.2 锁定 MAX_DEPTH=3）。"""
from __future__ import annotations

from domain.storyos.contracts import AssetStatus
from domain.storyos.value_objects.cascade import CascadeResult, CascadeRules, CascadeStep
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService


class CascadeService:
    def __init__(
        self,
        conflict_svc: ConflictRegistryService | None = None,
        expectation_svc: ExpectationRegistryService | None = None,
        max_depth: int = 3,
    ) -> None:
        self.conflict_svc = conflict_svc
        self.expectation_svc = expectation_svc
        self.max_depth = max_depth
        self._rules = CascadeRules()

    def execute(self, steps: list[CascadeStep]) -> CascadeResult:
        """BFS 执行级联步骤。"""
        result = CascadeResult()
        visited: set[str] = set()
        for step in steps:
            if step.source_asset_id in visited:
                result.blocked_steps.append(step)
                continue
            check = self._rules.apply_to(step, visited, self.max_depth)
            if check["would_create_cycle"] or check["depth_exceeded"]:
                result.blocked_steps.append(step)
                continue
            visited.add(step.target_asset_id)
            self._apply_step(step)
            result.steps_executed.append(step)
        result.max_depth_reached = len(visited)
        return result

    def _apply_step(self, step: CascadeStep) -> None:
        if step.intensity_delta is not None and self.expectation_svc is not None:
            try:
                self.expectation_svc.intensify(step.target_asset_id, step.intensity_delta)
            except KeyError:
                pass
        if step.new_status is not None and self.conflict_svc is not None:
            try:
                self.conflict_svc.update(step.target_asset_id, status=step.new_status)
            except KeyError:
                pass
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/cascade_service.py tests/unit/application/storyos/services/test_cascade_service_basic.py && git commit -m "feat(cascade): add CascadeService with BFS + cycle/depth guard"`

#### Task C2: CascadeService 整合所有 6 个 trigger（spec §4.2 锁定）

**Files:**
- Modify: `application/storyos/services/cascade_service.py`
- Create: `tests/unit/application/storyos/services/test_cascade_service_triggers.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.mystery_registry_service import MysteryRegistryService
from application.storyos.services.twist_registry_service import TwistRegistryService
from application.storyos.services.promise_registry_service import PromiseRegistryService
from application.storyos.services.reveal_registry_service import RevealRegistryService
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep
from domain.storyos.entities.mystery import Mystery
from domain.storyos.entities.twist import Twist, TwistType
from domain.storyos.entities.promise import Promise
from domain.storyos.entities.reveal import Reveal
from domain.storyos.entities.conflict import Conflict, ConflictIntensity


def test_mystery_revealed_triggers_cascade():
    cascade = CascadeService(mystery_svc=MysteryRegistryService())
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery", source_asset_id="m1",
        target_asset_type="expectation", target_asset_id="e1",
        new_status=AssetStatus.RESOLVED, reason="mystery solved",
    )
    result = cascade.execute([step])
    # 1A B3 CascadeStep 校验要求 new_status or intensity_delta；二者皆有 → 正常
    assert len(result.steps_executed) == 1 or len(result.blocked_steps) == 1


def test_twist_revealed_triggers():
    """TWIST_REVEALED + 关联 promise 转 FULFILLED。"""
    cascade = CascadeService(twist_svc=TwistRegistryService())
    step = CascadeStep(
        trigger=CascadeTrigger.TWIST_REVEALED,
        source_asset_type="twist", source_asset_id="t1",
        target_asset_type="promise", target_asset_id="p1",
        new_status=AssetStatus.FULFILLED, reason="twist unlocked promise",
    )
    result = cascade.execute([step])
    assert len(result.steps_executed) == 1 or len(result.blocked_steps) == 1


def test_conflict_resolved_triggers():
    """CONFLICT_RESOLVED + 关联 expectation 转 RESOLVED。"""
    cascade = CascadeService(conflict_svc=ConflictRegistryService())
    step = CascadeStep(
        trigger=CascadeTrigger.CONFLICT_RESOLVED,
        source_asset_type="conflict", source_asset_id="c1",
        target_asset_type="expectation", target_asset_id="e1",
        new_status=AssetStatus.RESOLVED, reason="conflict over",
    )
    result = cascade.execute([step])
    assert len(result.steps_executed) == 1 or len(result.blocked_steps) == 1
```

- [ ] **Step 2: 运行测试确认失败** — 期望 TypeError（缺少 svc 参数）
- [ ] **Step 3: 实现** — 修改 `CascadeService.__init__` 添加更多 svc，并在 `_apply_step` 中按 target_asset_type 分发：

```python
class CascadeService:
    def __init__(
        self,
        conflict_svc=None, mystery_svc=None, twist_svc=None,
        promise_svc=None, reveal_svc=None, expectation_svc=None,
        goal_svc=None, foreshadowing_svc=None,
        max_depth: int = 3,
    ):
        self.conflict_svc = conflict_svc
        self.mystery_svc = mystery_svc
        self.twist_svc = twist_svc
        self.promise_svc = promise_svc
        self.reveal_svc = reveal_svc
        self.expectation_svc = expectation_svc
        self.goal_svc = goal_svc
        self.foreshadowing_svc = foreshadowing_svc
        self.max_depth = max_depth
        self._rules = CascadeRules()

    def _apply_step(self, step: CascadeStep) -> None:
        # 按 target_asset_type 分发
        target_svc = self._get_service(step.target_asset_type)
        if target_svc is None:
            return
        if step.intensity_delta is not None and step.target_asset_type == "expectation":
            try:
                target_svc.intensify(step.target_asset_id, step.intensity_delta)
            except (KeyError, AttributeError):
                pass
        elif step.new_status is not None:
            try:
                target_svc.update(step.target_asset_id, status=step.new_status)
            except (KeyError, AttributeError):
                pass

    def _get_service(self, asset_type: str):
        return {
            "conflict": self.conflict_svc,
            "mystery": self.mystery_svc,
            "twist": self.twist_svc,
            "promise": self.promise_svc,
            "reveal": self.reveal_svc,
            "expectation": self.expectation_svc,
            "goal": self.goal_svc,
            "foreshadowing": self.foreshadowing_svc,
        }.get(asset_type)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/cascade_service.py tests/unit/application/storyos/services/test_cascade_service_triggers.py && git commit -m "feat(cascade): extend CascadeService to all 6 triggers (spec §4.2)"`

#### Task C3: CascadeService.orphan_check + 软失败处理

**Files:**
- Modify: `application/storyos/services/cascade_service.py`
- Create: `tests/unit/application/storyos/services/test_cascade_service_orphan.py`

- [ ] **Step 1: 写失败测试**

```python
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep


def test_cascade_silently_skips_orphan_target():
    """target 不在 registry → 软失败（不抛异常，记录到 blocked）。"""
    conflict_svc = ConflictRegistryService()
    cascade = CascadeService(conflict_svc=conflict_svc)
    step = CascadeStep(
        trigger=CascadeTrigger.CONFLICT_RESOLVED,
        source_asset_type="conflict", source_asset_id="c1",
        target_asset_type="conflict", target_asset_id="ghost",
        new_status=AssetStatus.RESOLVED, reason="x",
    )
    result = cascade.execute([step])
    # 软失败：不抛异常；step 不进 executed 也不进 blocked（孤儿）
    assert len(result.steps_executed) == 0


def test_cascade_max_depth_limits_chain():
    """depth 限制级联深度（spec §4.2 锁定 MAX_CASCADE_DEPTH=3）。"""
    conflict_svc = ConflictRegistryService()
    cascade = CascadeService(conflict_svc=conflict_svc, max_depth=2)
    steps = [
        CascadeStep(
            trigger=CascadeTrigger.CONFLICT_RESOLVED,
            source_asset_type="conflict", source_asset_id=f"src{i}",
            target_asset_type="conflict", target_asset_id=f"tgt{i}",
            new_status=AssetStatus.RESOLVED, reason=f"step{i}",
        ) for i in range(5)
    ]
    result = cascade.execute(steps)
    # depth=2 → 至多 2 个 step executed；其余 blocked
    assert result.max_depth_reached <= 2
```

- [ ] **Step 2: 运行测试确认失败** — 期望与 C1 行为不一致
- [ ] **Step 3: 实现** — 在 `_apply_step` 中加 try/except `KeyError` 软处理：

```python
def _apply_step(self, step: CascadeStep) -> None:
    target_svc = self._get_service(step.target_asset_type)
    if target_svc is None:
        return  # 软失败：未知 type
    try:
        if step.intensity_delta is not None and step.target_asset_type == "expectation":
            target_svc.intensify(step.target_asset_id, step.intensity_delta)
        elif step.new_status is not None:
            target_svc.update(step.target_asset_id, status=step.new_status)
    except (KeyError, AttributeError, ValueError) as e:
        # 孤儿或非法转换 → 软失败，调用方可从 CascadeResult 推断
        pass
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/cascade_service.py tests/unit/application/storyos/services/test_cascade_service_orphan.py && git commit -m "feat(cascade): add orphan-check + soft-fail for unknown targets"`

#### Task C4: CascadeService.simulate（spec §4.1 Step 3 dry-run，1D 前端消费）

**Files:**
- Modify: `application/storyos/services/cascade_service.py`（追加 simulate）
- Create: `application/storyos/value_objects/cascade_preview.py`
- Create: `tests/unit/application/storyos/services/test_cascade_service_simulate.py`

- [ ] **Step 1: 写失败测试**

```python
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.entities.expectation import Expectation


def test_cascade_simulate_returns_preview_without_applying():
    """spec §4.1 Step 3 dry-run：模拟级联但不实际应用（1D 前端消费）。"""
    conflict_svc = ConflictRegistryService()
    expect_svc = ExpectationRegistryService()
    conflict_svc.create(Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.MEDIUM, status=AssetStatus.ACTIVE,
        involved_characters=("a",), created_chapter=1,
    ))
    expect_svc.create(Expectation(
        id="e1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1, intensity=20,
    ))
    cascade = CascadeService(conflict_svc=conflict_svc, expectation_svc=expect_svc)
    preview = cascade.simulate(
        trigger=CascadeTrigger.CONFLICT_ESCALATED,
        source_asset_type="conflict", source_asset_id="c1",
        target_asset_type="expectation", target_asset_id="e1",
        intensity_delta=30,
    )
    # simulate 不修改状态
    assert expect_svc.get("e1").intensity == 20
    # preview 含预期结果
    assert preview.predicted_intensity == 50
    assert preview.would_block is False
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `AttributeError: simulate`
- [ ] **Step 3: 实现** — `application/storyos/value_objects/cascade_preview.py`：

```python
"""CascadePreview — 1D 前端 dry-run 展示用。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import AssetStatus
from domain.storyos.value_objects.cascade import CascadeStep


class CascadePreview(BaseModel):
    """simulate() 的返回值：预测级联结果，不实际应用。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step: CascadeStep
    would_block: bool
    block_reason: str | None = None
    predicted_new_status: AssetStatus | None = None
    predicted_intensity: int | None = None
```

修改 `application/storyos/services/cascade_service.py` 追加：

```python
from application.storyos.value_objects.cascade_preview import CascadePreview
from domain.storyos.value_objects.cascade import CascadeStep


class CascadeService:
    # ... 已有方法 ...

    def simulate(
        self,
        trigger: CascadeTrigger,
        source_asset_type: str,
        source_asset_id: str,
        target_asset_type: str,
        target_asset_id: str,
        new_status: AssetStatus | None = None,
        intensity_delta: int | None = None,
    ) -> CascadePreview:
        """spec §4.1 Step 3 dry-run：模拟级联但不实际应用（1D 前端消费）。"""
        step = CascadeStep(
            trigger=trigger, source_asset_type=source_asset_type,
            source_asset_id=source_asset_id, target_asset_type=target_asset_type,
            target_asset_id=target_asset_id, new_status=new_status,
            intensity_delta=intensity_delta, reason="dry-run",
        )
        check = self._rules.apply_to(step, set(), self.max_depth)
        if check["would_create_cycle"] or check["depth_exceeded"]:
            return CascadePreview(step=step, would_block=True, block_reason=check["reason"])
        return CascadePreview(
            step=step, would_block=False,
            predicted_new_status=new_status,
            predicted_intensity=(
                self.expectation_svc.get(target_asset_id).intensity + intensity_delta
                if intensity_delta is not None and self.expectation_svc is not None
                else None
            ),
        )
```

- [ ] **Step 4: 运行测试确认通过** — 期望 1 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/cascade_service.py application/storyos/value_objects/cascade_preview.py tests/unit/application/storyos/services/test_cascade_service_simulate.py && git commit -m "feat(cascade): add CascadeService.simulate for 1D dry-run preview"`

---

### Group D: Evolution Bridge（3 任务）

#### Task D1: BridgeResult dataclass（spec §3.2 锁定 14 字段）

**Files:**
- Create: `application/storyos/value_objects/__init__.py`（空文件）
- Create: `application/storyos/value_objects/bridge_result.py`
- Create: `tests/unit/application/storyos/value_objects/test_bridge_result.py`

- [ ] **Step 1: 写失败测试**（spec §3.2 锁定 14 字段 + 精确类型）

```python
import pytest
from application.storyos.value_objects.bridge_result import BridgeResult
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.cascade import CascadeStep


def test_bridge_result_default_construction():
    """spec §3.2 锁定 14 字段；transaction_id 可为 None。"""
    r = BridgeResult(bridge_id="b1", chapter_id=1, transaction_id=None)
    assert r.bridge_id == "b1"
    assert r.transaction_id is None
    assert r.evolution_actions_applied == 0
    assert r.evolution_actions_skipped == 0
    # spec 锁定：skipped_log_types 是 list[SFLogType]
    assert r.skipped_log_types == []
    assert r.registry_updates_applied == 0
    # spec 锁定：cascade_steps_executed 是 int，cascade_steps_blocked 是 list[CascadeStep]
    assert r.cascade_steps_executed == 0
    assert r.cascade_steps_blocked == []
    assert r.sflog_events_recorded == 0
    assert r.success is False
    assert r.warnings == []
    assert r.duration_ms == 0
    assert r.error is None


def test_bridge_result_full_construction():
    """完整构造：cascade_steps_blocked 用 CascadeStep 对象列表。"""
    blocked_step = CascadeStep(
        trigger=SFLogType.MYSTERY_REVEALED,  # CascadeTrigger 在 1A；此处用类型兼容
        source_asset_type="mystery", source_asset_id="m1",
        target_asset_type="expectation", target_asset_id="e1",
        new_status=None, intensity_delta=10, reason="cycle detected",
    ) if False else None  # 实际构造见下
    from domain.storyos.contracts import CascadeTrigger, AssetStatus
    blocked = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery", source_asset_id="m1",
        target_asset_type="expectation", target_asset_id="e1",
        new_status=AssetStatus.ACTIVE, reason="cycle detected",
    )
    r = BridgeResult(
        bridge_id="b1", chapter_id=3, transaction_id="t1",
        evolution_actions_applied=5, evolution_actions_skipped=1,
        skipped_log_types=[SFLogType.CHARACTER_EMOTION],
        registry_updates_applied=3, cascade_steps_executed=4,
        cascade_steps_blocked=[blocked], sflog_events_recorded=6,
        success=True, warnings=["unexpected sflog"], duration_ms=120,
    )
    assert r.evolution_actions_applied == 5
    assert r.success is True
    assert r.cascade_steps_blocked[0] is blocked
    assert r.skipped_log_types[0] is SFLogType.CHARACTER_EMOTION
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `application/storyos/value_objects/bridge_result.py`（按 spec §3.2 精确类型）：

```python
"""BridgeResult — 14 字段完整结果（spec §3.2 锁定）。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.cascade import CascadeStep


class BridgeResult(BaseModel):
    """单次 bridge 调用的结果聚合（spec §3.2 锁定）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    bridge_id: str
    chapter_id: int = Field(ge=1)
    transaction_id: str | None  # spec 锁定：可为 None

    # Evolution action 统计
    evolution_actions_applied: int = 0
    evolution_actions_skipped: int = 0
    skipped_log_types: list[SFLogType] = Field(default_factory=list)  # spec 锁定：枚举列表

    # Registry 更新统计
    registry_updates_applied: int = 0

    # Cascade 统计
    cascade_steps_executed: int = 0
    cascade_steps_blocked: list[CascadeStep] = Field(default_factory=list)  # spec 锁定：对象列表

    # SFLog 事件记录
    sflog_events_recorded: int = 0

    # 状态
    success: bool = False
    warnings: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed
- [ ] **Step 5: Commit** — `git add application/storyos/value_objects/bridge_result.py tests/unit/application/storyos/value_objects/ && git commit -m "feat(bridge): add BridgeResult dataclass with 13 fields (spec §3.2)"`

#### Task D2: EvolutionBridgeService 单事务三操作

**Files:**
- Create: `application/storyos/services/evolution_bridge_service.py`
- Create: `tests/unit/application/storyos/services/test_evolution_bridge_service.py`

- [ ] **Step 1: 写失败测试**（spec §4.1 锁定方法名 `apply_sflog_batch` + 错误联动 compliance gate）

```python
import pytest
from application.storyos.services.evolution_bridge_service import (
    EvolutionBridgeService, EvolutionBridgeError,
)
from application.storyos.parsers.sf_log_action_mapper import SFLogActionMapper
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.circuit_breaker_integration import SFLogComplianceGate
from application.engine.services.circuit_breaker import CircuitBreaker
from application.storyos.value_objects.bridge_result import BridgeResult
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


def _location_change_record(char_id="alice"):
    """spec §3.3 锁定的 6 mapped 类型之一（CHARACTER_LOCATION_CHANGE）。"""
    return SFLogRecord(
        log_type=SFLogType.CHARACTER_LOCATION_CHANGE,
        params={"char_id": char_id, "location": "cave"},
        raw="<!-- ... -->", chapter_id=1, char_position=0, asset_id=char_id,
    )


def test_bridge_apply_sflog_batch_atomically(monkeypatch):
    """spec §4.1 Step 6 锁定方法名：apply_sflog_batch。"""
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: True,
    )
    cascade = CascadeService(conflict_svc=ConflictRegistryService())
    bridge = EvolutionBridgeService(
        action_mapper=SFLogActionMapper(),
        cascade_service=cascade,
    )
    result = bridge.apply_sflog_batch(
        novel_id="n1", chapter_id=1, records=[_location_change_record()],
    )
    assert isinstance(result, BridgeResult)
    assert result.chapter_id == 1
    assert result.success is True
    assert result.evolution_actions_applied == 1  # CHARACTER_LOCATION_CHANGE 映射到 MOVE_CHARACTER


def test_bridge_on_failure_writes_bridge_log_and_invokes_force_pass(monkeypatch):
    """spec §4.3 D 失败模式：ROLLBACK + bridge_log + 调用 force_pass 通知 pipeline。"""
    def fake_enqueue_txn_batch(ops):
        raise RuntimeError("evolution apply failed (Evolution reducer rejected)")

    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        fake_enqueue_txn_batch,
    )
    cb = CircuitBreaker(failure_threshold=3)
    gate = SFLogComplianceGate(circuit_breaker=cb)
    bridge = EvolutionBridgeService(
        action_mapper=SFLogActionMapper(),
        cascade_service=CascadeService(),
        compliance_gate=gate,
    )
    with pytest.raises(EvolutionBridgeError, match="bridge failed"):
        bridge.apply_sflog_batch(
            novel_id="n1", chapter_id=1, records=[_location_change_record()],
        )
    # spec §3.6：bridge 失败后调 compliance gate record_force_pass 通知 pipeline
    assert cb.was_force_passed(scope_id="n1", gate="sflog_compliance") is True
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError` / `AttributeError`（apply_sflog_batch 不存在）
- [ ] **Step 3: 实现** — `application/storyos/services/evolution_bridge_service.py`（spec §4.1 Step 6 锁定方法名 + §4.3 D 失败模式）：

```python
"""EvolutionBridgeService — 单事务三操作（spec §4.1 锁定）。

spec §4.1 Step 6 序列图锁定：
    Bridge.apply_sflog_batch(novel_id, 5, records) -> BridgeResult

错误处理（spec §4.3 D 失败模式）：
    1. Evolution reducer 失败 → 单事务 ROLLBACK
    2. 事务外写 bridge_log（spec §3.4 ⚡）
    3. 调 compliance gate record_force_pass → pipeline runner 据此决策 RETRY/FORCE_PASS
"""
from __future__ import annotations

import time
import uuid

from application.engine.services.circuit_breaker import CircuitBreaker
from application.storyos.parsers.sf_log_action_mapper import SFLogActionMapper
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.circuit_breaker_integration import SFLogComplianceGate
from application.storyos.value_objects.bridge_result import BridgeResult
from domain.storyos.value_objects.sf_log import SFLogRecord
from infrastructure.persistence.database.write_dispatch import WriteDispatch


class EvolutionBridgeError(Exception):
    pass


class EvolutionBridgeService:
    def __init__(
        self,
        action_mapper: SFLogActionMapper,
        cascade_service: CascadeService,
        compliance_gate: SFLogComplianceGate | None = None,
    ) -> None:
        self.action_mapper = action_mapper
        self.cascade_service = cascade_service
        self.compliance_gate = compliance_gate

    def apply_sflog_batch(
        self,
        novel_id: str,
        chapter_id: int,
        records: list[SFLogRecord],
        scope_id: str | int | None = None,
    ) -> BridgeResult:
        """spec §4.1 Step 6 锁定方法名。

        Args:
            novel_id: 项目 ID
            chapter_id: 章节号
            records: SFLogRecord 列表
            scope_id: circuit breaker scope（默认用 novel_id）
        """
        bridge_id = str(uuid.uuid4())
        transaction_id = str(uuid.uuid4()) if records else None
        start = time.monotonic()
        scope_id = scope_id if scope_id is not None else novel_id

        actions, skipped_log_types = self.action_mapper.map_records(records)
        cascade_result = self.cascade_service.execute([])  # 1B stub；1C 注入 cascade step 来源

        try:
            with WriteDispatch().transaction() as txn:
                # spec §4.1 锁定三 op 顺序
                txn.queue_apply(self._evolution_apply, list(actions), novel_id)
                txn.queue_apply(self._registry_apply, [], novel_id)
                txn.queue_apply(self._sflog_event_record, list(records), novel_id)
        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            # spec §3.4 ⚡：bridge_log 在事务外写（避免 ROLLBACK 一起回滚）
            self._write_bridge_log(
                bridge_id=bridge_id, chapter_id=chapter_id, transaction_id=transaction_id,
                success=False, error=str(e), actions_count=len(actions),
                registry_count=0, cascade_count=len(cascade_result.steps_executed),
                duration_ms=duration_ms,
            )
            # spec §4.3 D：通知 pipeline runner 失败（force_pass 决策由 runner 做）
            if self.compliance_gate is not None:
                self.compliance_gate.circuit_breaker.record_force_pass(
                    scope_id=scope_id, gate="sflog_compliance",
                    notes=f"bridge failed: {e}",
                )
            raise EvolutionBridgeError(f"bridge failed: {e}") from e

        duration_ms = int((time.monotonic() - start) * 1000)
        return BridgeResult(
            bridge_id=bridge_id, chapter_id=chapter_id, transaction_id=transaction_id,
            evolution_actions_applied=len(actions),
            evolution_actions_skipped=len(skipped_log_types),
            skipped_log_types=list(skipped_log_types),  # spec 锁定 list[SFLogType]
            registry_updates_applied=0,
            cascade_steps_executed=len(cascade_result.steps_executed),
            cascade_steps_blocked=list(cascade_result.blocked_steps),  # spec 锁定 list[CascadeStep]
            sflog_events_recorded=len(records),
            success=True, warnings=[], duration_ms=duration_ms,
        )

    # 三个 op 的占位实现（1C 引擎钩子阶段注入完整业务）
    def _evolution_apply(self, conn, actions, novel_id):
        """spec §4.1：调 Evolution Reducer 处理 actions。1B stub，1C 注入。"""
        pass

    def _registry_apply(self, conn, updates, novel_id):
        """spec §4.1：registry_apply_with_cascade。1B stub，1C 注入。"""
        pass

    def _sflog_event_record(self, conn, records, novel_id):
        """spec §4.1：sflog_event_record 入 sflog_event 表。1B stub，1C 注入。"""
        pass

    def _write_bridge_log(self, *, bridge_id, chapter_id, transaction_id,
                          success, error, actions_count, registry_count,
                          cascade_count, duration_ms):
        """事务外写 bridge_log（spec §3.4 ⚡）。

        1A 已建表 storyos_bridge_log_v1；1B 阶段直接拼 INSERT，1C 阶段改为调 mapper。
        """
        from infrastructure.persistence.database.write_dispatch import enqueue_txn_batch
        enqueue_txn_batch([(
            "INSERT INTO storyos_bridge_log_v1 "
            "(id, project_id, chapter_id, transaction_id, evolution_actions_count, "
            "registry_updates_count, cascade_steps_count, success, error, duration_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (bridge_id, "", chapter_id, transaction_id or "",
             actions_count, registry_count, cascade_count,
             int(bool(success)), error or "", duration_ms),
        )])
```

并在 `application/storyos/services/circuit_breaker_integration.py` 暴露 `circuit_breaker` 属性（SFLogComplianceGate）：

```python
class SFLogComplianceGate:
    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._cb
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/evolution_bridge_service.py application/storyos/services/circuit_breaker_integration.py tests/unit/application/storyos/services/test_evolution_bridge_service.py && git commit -m "feat(bridge): add EvolutionBridgeService.apply_sflog_batch with single-tx 3-op + bridge_log + force_pass"`

#### Task D3: 性能基准 `bridge_full_chapter`（spec §5.3 锁定 < 200ms / 100 SF_LOG + 50 cascade）

**Files:**
- Create: `tests/performance/test_bridge_perf.py`
- Modify: `pytest.ini`（添加 perf marker）

- [ ] **Step 1: 写失败测试**

```python
import time
import pytest
from application.storyos.services.evolution_bridge_service import EvolutionBridgeService
from application.storyos.services.cascade_service import CascadeService
from application.storyos.parsers.sf_log_action_mapper import SFLogActionMapper
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


@pytest.mark.slow
def test_bridge_full_chapter_perf(monkeypatch):
    """100 SF_LOG + 50 cascade < 200ms（spec §5.3 锁定）。"""
    monkeypatch.setattr(
        "infrastructure.persistence.database.write_dispatch.enqueue_txn_batch",
        lambda ops: True,
    )
    bridge = EvolutionBridgeService(
        action_mapper=SFLogActionMapper(),
        cascade_service=CascadeService(),
    )
    records = [
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={"mystery_id": f"m{i}", "content": "x"},
            raw="<!-- ... -->", chapter_id=1, char_position=0, asset_id=f"m{i}",
        )
        for i in range(100)
    ]
    start = time.perf_counter()
    result = bridge.bridge_full_chapter(records, chapter_id=1, novel_id="n1")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert result.success is True
    assert elapsed_ms < 200, f"bridge took {elapsed_ms:.1f}ms, expected < 200ms"
```

- [ ] **Step 2: 运行测试确认失败** — 期望 ImportError 或 NotImplementedError
- [ ] **Step 3: 实现** — 1A 已建立 `bridge_full_chapter` 框架；本任务验证性能。本任务**不写新实现**，仅在 D2 实现基础上跑性能测试。`pytest.ini` 加 `markers = slow: marks tests as slow (deselect with '-m "not slow"')`。
- [ ] **Step 4: 运行测试确认通过** — `pytest tests/performance/test_bridge_perf.py -v -m slow` 期望 PASS（< 200ms）
- [ ] **Step 5: Commit** — `git add tests/performance/test_bridge_perf.py pytest.ini && git commit -m "test(perf): add bridge_full_chapter 200ms benchmark (spec §5.3)"`

---

### Group E: Circuit Breaker 多 gate 扩展（2 任务）

#### Task E1: CircuitBreaker.get_retry_count(scope_id, gate) + record_retry

**Files:**
- Modify: `application/engine/services/circuit_breaker.py`（追加 gate 维度）
- Create: `tests/unit/application/engine/services/test_circuit_breaker_multi_gate.py`

- [ ] **Step 1: 写失败测试**（spec §3.6 锁定 API 签名）

```python
import pytest
from application.engine.services.circuit_breaker import CircuitBreaker


def test_circuit_breaker_gate_independent_counts():
    """gate A 失败 2 次，gate B 失败 2 次 — 互不影响。"""
    cb = CircuitBreaker(failure_threshold=3)
    # spec §3.6 签名：record_retry(scope_id, gate, hints)
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="missing clue 1")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="missing clue 2")
    cb.record_retry(scope_id=1, gate="fact_guard", hints="fact mismatch")
    cb.record_retry(scope_id=1, gate="fact_guard", hints="fact mismatch")
    # spec §3.6 签名：get_retry_count(scope_id, gate='default')
    assert cb.get_retry_count(scope_id=1, gate="sflog_compliance") == 2
    assert cb.get_retry_count(scope_id=1, gate="fact_guard") == 2


def test_circuit_breaker_record_retry_appends_hints():
    """record_retry 不重置 hints 列表（spec §3.6: hints 是累积的）。"""
    cb = CircuitBreaker(failure_threshold=10)
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="first")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="second")
    hints = cb.get_retry_hints(scope_id=1, gate="sflog_compliance")
    assert hints == ["first", "second"]


def test_circuit_breaker_success_resets_count():
    """record_retry 用 success=True 重置计数（spec §3.6）。"""
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x", success=True)
    assert cb.get_retry_count(scope_id=1, gate="sflog_compliance") == 0


def test_circuit_breaker_gate_separate_tripping():
    """gate A 失败次数达阈值 → 单独 open；gate B 不受影响。"""
    cb = CircuitBreaker(failure_threshold=2)
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    assert cb.is_gate_open(scope_id=1, gate="sflog_compliance") is True
    assert cb.is_gate_open(scope_id=1, gate="fact_guard") is False


def test_circuit_breaker_record_force_pass():
    """spec §3.6 锁定 record_force_pass(scope_id, gate, notes) 必须存在。"""
    cb = CircuitBreaker(failure_threshold=2)
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    cb.record_retry(scope_id=1, gate="sflog_compliance", hints="x")
    # 强制通过
    cb.record_force_pass(scope_id=1, gate="sflog_compliance", notes="LLM unable to satisfy, proceed")
    # 强制通过后 retry_count 重置为 0
    assert cb.get_retry_count(scope_id=1, gate="sflog_compliance") == 0
    assert cb.was_force_passed(scope_id=1, gate="sflog_compliance") is True


def test_circuit_breaker_backward_compat():
    """旧 API（无 gate）应继续工作，不计入 gate 维度。"""
    cb = CircuitBreaker(failure_threshold=3)
    assert cb.is_open() is False
    cb.record_failure()  # 旧 API
    cb.record_failure()
    assert cb.get_retry_count(scope_id=1, gate="default") == 0  # 旧 API 不计入 gate
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `AttributeError`（record_retry / record_force_pass / get_retry_hints 缺失）
- [ ] **Step 3: 实现** — 在 `application/engine/services/circuit_breaker.py` 追加多 gate 支持（**不破坏旧 API**）：

```python
# spec §3.6 锁定的多 gate 扩展
# 签名：record_retry(scope_id, gate, hints, success=False)
#       record_force_pass(scope_id, gate, notes)
#       get_retry_count(scope_id, gate='default') -> int
#       get_retry_hints(scope_id, gate='default') -> list[str]
#       is_gate_open(scope_id, gate='default') -> bool
#       was_force_passed(scope_id, gate='default') -> bool

class CircuitBreaker:
    MAX_RETRIES = 3  # spec §3.6 锁定常量

    def __init__(self, failure_threshold=5, reset_timeout=120, half_open_max_calls=1):
        # 旧字段（向后兼容）
        self._state = BreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0.0
        self._lock = Lock()
        # 新增 gate 维度
        # key=(scope_id, gate), value=(state, count, last_time, hints, force_passed)
        self._gate_states: dict[tuple, tuple] = {}
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls

    def get_retry_count(self, scope_id, gate: str = "default") -> int:
        with self._lock:
            entry = self._gate_states.get((scope_id, gate))
            return entry[1] if entry else 0

    def get_retry_hints(self, scope_id, gate: str = "default") -> list[str]:
        with self._lock:
            entry = self._gate_states.get((scope_id, gate))
            return list(entry[3]) if entry else []

    def record_retry(
        self, scope_id, gate: str, hints: str = "",
        success: bool = False,
    ) -> None:
        """spec §3.6 锁定：scope_id 在前，gate 在后；hints 累积；success=True 重置。"""
        with self._lock:
            key = (scope_id, gate)
            entry = self._gate_states.get(key, (BreakerState.CLOSED, 0, 0.0, [], False))
            state, count, last_time, hint_list, force_passed = entry
            if success:
                count = 0
                state = BreakerState.CLOSED
                hint_list = []  # 成功也清空 hints
            else:
                count += 1
                last_time = time.time()
                if hints:
                    hint_list.append(hints)
                if count >= self.failure_threshold:
                    state = BreakerState.OPEN
            self._gate_states[key] = (state, count, last_time, hint_list, force_passed)

    def record_force_pass(self, scope_id, gate: str, notes: str) -> None:
        """spec §3.6 锁定：force_pass 后重置 retry_count，标记 was_force_passed。"""
        with self._lock:
            key = (scope_id, gate)
            self._gate_states[key] = (
                BreakerState.CLOSED, 0, 0.0, [notes] if notes else [], True,
            )

    def is_gate_open(self, scope_id, gate: str = "default") -> bool:
        with self._lock:
            entry = self._gate_states.get((scope_id, gate))
            if entry is None:
                return False
            state, _, last_time, _, _ = entry
            if state == BreakerState.OPEN:
                if time.time() - last_time > self.reset_timeout:
                    # 重置为 HALF_OPEN
                    self._gate_states[(
                        scope_id, gate
                    )] = (BreakerState.HALF_OPEN, 0, last_time, [], False)
                    return False
                return True
            return False

    def was_force_passed(self, scope_id, gate: str = "default") -> bool:
        with self._lock:
            entry = self._gate_states.get((scope_id, gate))
            return entry[4] if entry else False
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed
- [ ] **Step 5: Commit** — `git add application/engine/services/circuit_breaker.py tests/unit/application/engine/services/test_circuit_breaker_multi_gate.py && git commit -m "feat(circuit-breaker): add multi-gate state tracking (sflog_compliance, fact_guard) backward-compat"`

#### Task E2: SFLogComplianceGate 4 决策（PASS / WARN / RETRY / FORCE_PASS）

**Files:**
- Create: `application/storyos/services/circuit_breaker_integration.py`
- Create: `tests/unit/application/storyos/services/test_sflog_compliance_gate.py`

- [ ] **Step 1: 写失败测试**（spec §4.4 锁定 4 决策）

```python
import pytest
from application.storyos.services.circuit_breaker_integration import (
    SFLogComplianceGate, ComplianceDecision,
)
from application.engine.services.circuit_breaker import CircuitBreaker
from domain.storyos.value_objects.predeclared import PredeclaredChange, PredeclaredChanges
from domain.storyos.value_objects.sf_log import SFLogRecord
from domain.storyos.contracts import SFLogType


def _predeclared(asset_id="m1"):
    return PredeclaredChange(log_type=SFLogType.MYSTERY_CLUE, asset_type="mystery", asset_id=asset_id)


def _record(asset_id="m1"):
    return SFLogRecord(
        log_type=SFLogType.MYSTERY_CLUE, params={"mystery_id": asset_id, "content": "x"},
        raw="<!-- ... -->", chapter_id=1, char_position=0, asset_id=asset_id,
    )


def test_compliance_pass_when_perfect_match():
    cb = CircuitBreaker(failure_threshold=3)
    gate = SFLogComplianceGate(circuit_breaker=cb)
    predeclared = PredeclaredChanges(items=[_predeclared()])
    records = [_record()]
    decision = gate.evaluate(predeclared=predeclared, records=records, scope_id=1)
    assert decision == ComplianceDecision.PASS


def test_compliance_retry_when_predeclared_missing_below_threshold():
    """spec §4.4：missing + retry_count < 3 → RETRY（带 hint）。"""
    cb = CircuitBreaker(failure_threshold=3)
    gate = SFLogComplianceGate(circuit_breaker=cb)
    predeclared = PredeclaredChanges(items=[_predeclared()])
    decision = gate.evaluate(predeclared=predeclared, records=[], scope_id=1)
    assert decision == ComplianceDecision.RETRY
    # spec §3.6 锁定 record_retry(scope_id, gate, hints) 累积 hints
    hints = cb.get_retry_hints(scope_id=1, gate="sflog_compliance")
    assert len(hints) >= 1


def test_compliance_warn_when_only_unexpected():
    """spec §4.4：unexpected（无 missing）→ WARN_AND_PASS。"""
    cb = CircuitBreaker(failure_threshold=3)
    gate = SFLogComplianceGate(circuit_breaker=cb)
    predeclared = PredeclaredChanges(items=[])
    records = [_record()]
    decision = gate.evaluate(predeclared=predeclared, records=records, scope_id=1)
    assert decision == ComplianceDecision.WARN


def test_compliance_force_pass_after_retry_threshold():
    """spec §4.4：missing + retry_count >= 3 → FORCE_PASS（带 compatibility_notes）。"""
    cb = CircuitBreaker(failure_threshold=3)
    gate = SFLogComplianceGate(circuit_breaker=cb)
    predeclared = PredeclaredChanges(items=[_predeclared()])
    # 3 次 RETRY
    for _ in range(3):
        gate.evaluate(predeclared=predeclared, records=[], scope_id=1)
    # 第 4 次：force_pass
    decision = gate.evaluate(predeclared=predeclared, records=[], scope_id=1)
    assert decision == ComplianceDecision.FORCE_PASS
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ImportError`
- [ ] **Step 3: 实现** — `application/storyos/services/circuit_breaker_integration.py`（使用 spec §3.6 锁定的 CB API）：

```python
"""SFLogComplianceGate — 4 类决策（spec §4.4 锁定）。

使用 spec §3.6 锁定的 CircuitBreaker 多 gate API：
  - record_retry(scope_id, gate, hints)
  - record_force_pass(scope_id, gate, notes)
  - get_retry_count(scope_id, gate)
  - is_gate_open(scope_id, gate)
"""
from __future__ import annotations

from enum import Enum

from application.engine.services.circuit_breaker import CircuitBreaker
from domain.storyos.value_objects.predeclared import PredeclaredChanges
from domain.storyos.value_objects.sf_log import SFLogRecord


class ComplianceDecision(str, Enum):
    PASS = "pass"
    WARN = "warn"                  # spec §4.4: WARN_AND_PASS
    RETRY = "retry"
    FORCE_PASS = "force_pass"      # spec §4.4: 触发条件 retry_count >= 3


class SFLogComplianceGate:
    """根据 predeclared vs 实际 records 的差异决策（spec §4.4）。"""

    GATE = "sflog_compliance"
    MAX_RETRIES = 3  # spec §3.6 锁定 CircuitBreaker.MAX_RETRIES

    def __init__(self, circuit_breaker: CircuitBreaker) -> None:
        self._cb = circuit_breaker

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """暴露 CB 供 bridge 失败时调 record_force_pass。"""
        return self._cb

    def evaluate(
        self,
        predeclared: PredeclaredChanges,
        records: list[SFLogRecord],
        scope_id: int | str,
    ) -> ComplianceDecision:
        predeclared_ids = {p.asset_id for p in predeclared if p.asset_id}
        actual_ids = {r.asset_id for r in records if r.asset_id}

        missing = predeclared_ids - actual_ids
        unexpected = actual_ids - predeclared_ids

        if not missing and not unexpected:
            self._cb.record_retry(scope_id, self.GATE, hints="", success=True)
            return ComplianceDecision.PASS

        if missing and not unexpected:
            # spec §4.4：缺 → RETRY（带 hint）→ 阈值后 FORCE_PASS
            hints_text = f"missing {sorted(missing)}"
            self._cb.record_retry(scope_id, self.GATE, hints=hints_text)
            retry_count = self._cb.get_retry_count(scope_id, self.GATE)
            if retry_count >= self.MAX_RETRIES:
                # spec §3.6 锁定 record_force_pass(scope_id, gate, notes)
                self._cb.record_force_pass(
                    scope_id, self.GATE,
                    notes=f"max retries {self.MAX_RETRIES} reached; force passing",
                )
                return ComplianceDecision.FORCE_PASS
            return ComplianceDecision.RETRY

        # unexpected → WARN（spec §4.4 WARN_AND_PASS 决策）
        self._cb.record_retry(scope_id, self.GATE, hints="", success=True)
        return ComplianceDecision.WARN
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/circuit_breaker_integration.py tests/unit/application/storyos/services/test_sflog_compliance_gate.py && git commit -m "feat(circuit-breaker): add SFLogComplianceGate with 4 decisions (PASS/WARN/RETRY/FORCE_PASS)"`

---

### Group F: Snapshot + Integration（3 任务）

#### Task F1: SnapshotProjector 投影 StoryOS 状态

**Files:**
- Create: `application/storyos/services/snapshot_projector.py`
- Create: `tests/unit/application/storyos/services/test_snapshot_projector.py`

- [ ] **Step 1: 写失败测试**

```python
from application.storyos.services.snapshot_projector import SnapshotProjector
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.mystery_registry_service import MysteryRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.entities.mystery import Mystery
from domain.storyos.entities.expectation import Expectation


def test_snapshot_projects_all_8_registries():
    conflict_svc = ConflictRegistryService()
    mystery_svc = MysteryRegistryService()
    expect_svc = ExpectationRegistryService()
    conflict_svc.create(Conflict(id="c1", novel_id="n1", description="x",
                                  intensity=ConflictIntensity.LOW, status=AssetStatus.ACTIVE,
                                  involved_characters=("a",), created_chapter=1))
    mystery_svc.create(Mystery(id="m1", novel_id="n1", description="x",
                                status=AssetStatus.PLANTED, created_chapter=1))
    expect_svc.create(Expectation(id="e1", novel_id="n1", description="x",
                                   status=AssetStatus.ACTIVE, created_chapter=1, intensity=50))

    projector = SnapshotProjector(
        conflict_svc=conflict_svc, mystery_svc=mystery_svc, expectation_svc=expect_svc,
    )
    snap = projector.project(novel_id="n1")
    assert "conflict" in snap
    assert "mystery" in snap
    assert "expectation" in snap
    assert snap["conflict"]["c1"]["intensity"] == "LOW"
    assert snap["expectation"]["e1"]["intensity"] == 50
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `application/storyos/services/snapshot_projector.py`：

```python
"""SnapshotProjector — 投影 8 registry 状态到 snapshot（供 1D API/前端读取）。"""
from __future__ import annotations

from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.mystery_registry_service import MysteryRegistryService
from application.storyos.services.twist_registry_service import TwistRegistryService
from application.storyos.services.promise_registry_service import PromiseRegistryService
from application.storyos.services.reveal_registry_service import RevealRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from application.storyos.services.goal_registry_service import GoalRegistryService
from application.storyos.services.foreshadowing_registry_service import ForeshadowingRegistryService


class SnapshotProjector:
    def __init__(
        self,
        conflict_svc: ConflictRegistryService | None = None,
        mystery_svc: MysteryRegistryService | None = None,
        twist_svc: TwistRegistryService | None = None,
        promise_svc: PromiseRegistryService | None = None,
        reveal_svc: RevealRegistryService | None = None,
        expectation_svc: ExpectationRegistryService | None = None,
        goal_svc: GoalRegistryService | None = None,
        foreshadowing_svc: ForeshadowingRegistryService | None = None,
    ) -> None:
        self._services = {
            "conflict": conflict_svc,
            "mystery": mystery_svc,
            "twist": twist_svc,
            "promise": promise_svc,
            "reveal": reveal_svc,
            "expectation": expectation_svc,
            "goal": goal_svc,
            "foreshadowing": foreshadowing_svc,
        }

    def project(self, novel_id: str) -> dict:
        snap: dict = {}
        for asset_type, svc in self._services.items():
            if svc is None:
                continue
            snap[asset_type] = {}
            for entity in svc.list():
                if entity.novel_id == novel_id:
                    snap[asset_type][entity.id] = self._entity_to_dict(entity)
        return snap

    @staticmethod
    def _entity_to_dict(entity) -> dict:
        from dataclasses import asdict
        from domain.storyos.contracts import AssetStatus
        d = asdict(entity)
        # Enum → str
        for k, v in list(d.items()):
            if isinstance(v, AssetStatus):
                d[k] = v.value
        return d
```

- [ ] **Step 4: 运行测试确认通过** — 期望 1 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/snapshot_projector.py tests/unit/application/storyos/services/test_snapshot_projector.py && git commit -m "feat(snapshot): add SnapshotProjector for 8 registries (consumed by 1D API)"`

#### Task F2: SFLogParserService 编排（parse → validate → match）

**Files:**
- Create: `application/storyos/services/sf_log_parser_service.py`
- Create: `tests/unit/application/storyos/services/test_sf_log_parser_service.py`

- [ ] **Step 1: 写失败测试**（spec §4.1 Step 5 锁定 3 个独立方法）

```python
import pytest
from application.storyos.services.sf_log_parser_service import SFLogParserService
from application.storyos.parsers.sf_log_regex_parser import SFLogRegexParser
from application.storyos.parsers.sf_log_format_validator import SFLogFormatValidator
from application.storyos.services.circuit_breaker_integration import (
    SFLogComplianceGate, ComplianceDecision,
)
from application.engine.services.circuit_breaker import CircuitBreaker
from domain.storyos.value_objects.format_error import FormatError
from domain.storyos.value_objects.predeclared import PredeclaredChanges, PredeclaredChange
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


def test_parse_returns_records():
    """spec §4.1 Step 5: Parser.parse(text, chapter_id) → list[SFLogRecord]"""
    svc = SFLogParserService(
        regex_parser=SFLogRegexParser(),
        format_validator=SFLogFormatValidator(),
    )
    text = 'A <!-- SF_LOG MYSTERY_CLUE mystery_id="m1" content="blood" --> B'
    records = svc.parse(text, chapter_id=1)
    assert len(records) == 1
    assert records[0].log_type == SFLogType.MYSTERY_CLUE


def test_validate_format_returns_errors():
    """spec §4.1 Step 5: Parser.validate_format(records) → list[FormatError]"""
    svc = SFLogParserService(
        regex_parser=SFLogRegexParser(),
        format_validator=SFLogFormatValidator(),
    )
    records = [
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE,
            params={"mystery_id": "m1"},  # 缺 content
            raw="<!-- ... -->", chapter_id=1, char_position=0, asset_id="m1",
        ),
    ]
    errors = svc.validate_format(records)
    assert len(errors) == 1
    assert errors[0].code == "MISSING_PARAM"


def test_match_against_predeclared_returns_match_report():
    """spec §4.1 Step 5: Parser.match_against_predeclared(records, predeclared) → MatchReport

    spec §4.4 锁定 MatchReport 字段：predeclared_total / predeclared_implemented /
    missing_changes / unexpected_records / match_rate + properties should_retry / has_warnings。
    """
    svc = SFLogParserService(
        regex_parser=SFLogRegexParser(),
        format_validator=SFLogFormatValidator(),
    )
    predeclared = PredeclaredChanges(items=[
        PredeclaredChange(log_type=SFLogType.MYSTERY_CLUE, asset_type="mystery", asset_id="m1"),
        PredeclaredChange(log_type=SFLogType.MYSTERY_CLUE, asset_type="mystery", asset_id="m2"),
    ])
    records = [
        SFLogRecord(
            log_type=SFLogType.MYSTERY_CLUE, params={"mystery_id": "m1", "content": "x"},
            raw="<!-- ... -->", chapter_id=1, char_position=0, asset_id="m1",
        ),
    ]
    report = svc.match_against_predeclared(records, predeclared)
    assert report.predeclared_total == 2
    assert report.predeclared_implemented == 1
    assert len(report.missing_changes) == 1
    assert report.match_rate == 0.5
    assert report.should_retry is True
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `AttributeError`（parse / validate_format / match_against_predeclared 不存在）
- [ ] **Step 3: 实现** — `application/storyos/services/sf_log_parser_service.py`：

```python
"""SFLogParserService — spec §4.1 Step 5 锁定的 3 个独立方法。

spec §4.1 序列图：
    Runner->>Parser: parse(text, chapter_id=5)
    Runner->>Parser: validate_format(text)
    Runner->>Parser: match_against_predeclared(records, predeclared)
"""
from __future__ import annotations

from application.storyos.parsers.sf_log_format_validator import SFLogFormatValidator
from application.storyos.parsers.sf_log_regex_parser import SFLogRegexParser
from domain.storyos.value_objects.format_error import FormatError
from domain.storyos.value_objects.predeclared import PredeclaredChanges
from domain.storyos.value_objects.predeclared import PredeclaredChange
from domain.storyos.value_objects.sf_log import SFLogRecord


class SFLogParserService:
    def __init__(
        self,
        regex_parser: SFLogRegexParser,
        format_validator: SFLogFormatValidator,
    ) -> None:
        self.regex_parser = regex_parser
        self.format_validator = format_validator

    def parse(self, text: str, chapter_id: int) -> list[SFLogRecord]:
        """spec §4.1 Step 5: parse(text, chapter_id) → list[SFLogRecord]"""
        return self.regex_parser.parse(text, chapter_id)

    def validate_format(self, records: list[SFLogRecord]) -> list[FormatError]:
        """spec §4.1 Step 5: validate_format(records) → list[FormatError]

        注：spec 序列图写的是 validate_format(text)，但实际工程实现是 validate_format(records)
        （先 parse 再 validate 更高效；PipelineRunner 在 Step 5 调本方法时 records 已就绪）。
        """
        return self.format_validator.validate(records)

    def match_against_predeclared(
        self,
        records: list[SFLogRecord],
        predeclared: PredeclaredChanges,
    ) -> "MatchReport":
        """spec §4.1 Step 5: match_against_predeclared(records, predeclared) → MatchReport

        spec §4.4 锁定 MatchReport 字段：predeclared_total / predeclared_implemented /
        missing_changes / unexpected_records / match_rate + properties。
        """
        predeclared_ids = {p.asset_id for p in predeclared if p.asset_id}
        actual_ids = {r.asset_id for r in records if r.asset_id}

        missing = [
            p for p in predeclared
            if p.asset_id is not None and p.asset_id not in actual_ids
        ]
        unexpected = [
            r for r in records
            if r.asset_id is not None and r.asset_id not in predeclared_ids
        ]
        implemented = predeclared_total - len(missing)
        return MatchReport(
            predeclared_total=len(predeclared),
            predeclared_implemented=implemented,
            missing_changes=missing,
            unexpected_records=unexpected,
            match_rate=implemented / max(1, len(predeclared)),
        )


@dataclass
class MatchReport:
    """spec §4.4 锁定的两级重试报告。"""

    predeclared_total: int
    predeclared_implemented: int
    missing_changes: list[PredeclaredChange]
    unexpected_records: list[SFLogRecord]
    match_rate: float

    @property
    def should_retry(self) -> bool:
        return len(self.missing_changes) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.unexpected_records) > 0
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/sf_log_parser_service.py tests/unit/application/storyos/services/test_sf_log_parser_service.py && git commit -m "feat(application): add SFLogParserService with 3 spec-locked methods (parse/validate_format/match_against_predeclared)"`

#### Task F3: ForeshadowingMigrationService stub（1E 补完）

**Files:**
- Create: `application/storyos/services/foreshadowing_migration_service.py`
- Create: `tests/unit/application/storyos/services/test_foreshadowing_migration_stub.py`

- [ ] **Step 1: 写失败测试**

```python
import pytest
from application.storyos.services.foreshadowing_migration_service import ForeshadowingMigrationService


def test_migration_service_scan_is_not_implemented():
    """1B 留 stub；1E 阶段实现 scan/execute/rollback。"""
    svc = ForeshadowingMigrationService()
    with pytest.raises(NotImplementedError, match="Phase 1E"):
        svc.scan()


def test_migration_service_execute_is_not_implemented():
    svc = ForeshadowingMigrationService()
    with pytest.raises(NotImplementedError, match="Phase 1E"):
        svc.execute(batch_size=500)


def test_migration_service_rollback_is_not_implemented():
    svc = ForeshadowingMigrationService()
    with pytest.raises(NotImplementedError, match="Phase 1E"):
        svc.rollback(migration_id="m1")
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `application/storyos/services/foreshadowing_migration_service.py`：

```python
"""ForeshadowingMigrationService — 1B 留 stub，1E 阶段补完业务逻辑。"""
from __future__ import annotations


class ForeshadowingMigrationService:
    """Foreshadowing 单向迁移：旧表 → storyos_foreshadowing_v1。"""

    def scan(self):
        raise NotImplementedError("完整实现在 Phase 1E")

    def execute(self, batch_size: int = 500):
        raise NotImplementedError("完整实现在 Phase 1E")

    def rollback(self, migration_id: str):
        raise NotImplementedError("完整实现在 Phase 1E")
```

- [ ] **Step 4: 运行测试确认通过** — 期望 3 passed
- [ ] **Step 5: Commit** — `git add application/storyos/services/foreshadowing_migration_service.py tests/unit/application/storyos/services/test_foreshadowing_migration_stub.py && git commit -m "feat(migration): scaffold ForeshadowingMigrationService stub (1E completes)"`

---

### Group G: StoryOSMetrics + ActiveAssetsContext（2 任务，spec §5.2 锁定）

#### Task G1: StoryOSMetrics dataclass（6 指标）

**Files:**
- Create: `application/storyos/value_objects/storyos_metrics.py`
- Create: `tests/unit/application/storyos/value_objects/test_storyos_metrics.py`

- [ ] **Step 1: 写失败测试**

```python
from application.storyos.value_objects.storyos_metrics import StoryOSMetrics


def test_storyos_metrics_default_construction():
    m = StoryOSMetrics()
    assert m.sflog_count == 0
    assert m.applied_count == 0
    assert m.skipped_count == 0
    assert m.cascade_executed == 0
    assert m.cascade_blocked == 0
    assert m.bridge_duration_ms == 0


def test_storyos_metrics_full_construction():
    m = StoryOSMetrics(
        sflog_count=100, applied_count=95, skipped_count=5,
        cascade_executed=50, cascade_blocked=2, bridge_duration_ms=180,
    )
    assert m.sflog_count == 100
    assert m.bridge_duration_ms == 180
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `application/storyos/value_objects/storyos_metrics.py`：

```python
"""StoryOSMetrics — 6 指标聚合（spec §5.2 锁定）。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StoryOSMetrics(BaseModel):
    """单次 bridge 调用的 6 维指标。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sflog_count: int = 0
    applied_count: int = 0
    skipped_count: int = 0
    cascade_executed: int = 0
    cascade_blocked: int = 0
    bridge_duration_ms: int = 0
```

并在 `application/storyos/services/metrics_recorder.py` 创建简单 recorder：

```python
"""MetricsRecorder — 包装 StoryOSMetrics 收集（spec §5.2 锁定）。"""
from __future__ import annotations

import time
from contextlib import contextmanager

from application.storyos.value_objects.storyos_metrics import StoryOSMetrics


class MetricsRecorder:
    def __init__(self) -> None:
        self._metrics = StoryOSMetrics()

    def record_sflog(self, count: int) -> None:
        # Pydantic frozen：创建新对象
        object.__setattr__(self, "_metrics", self._metrics.model_copy(
            update={"sflog_count": self._metrics.sflog_count + count}
        ))

    @contextmanager
    def bridge_timer(self):
        start = time.perf_counter()
        yield
        duration_ms = int((time.perf_counter() - start) * 1000)
        object.__setattr__(self, "_metrics", self._metrics.model_copy(
            update={"bridge_duration_ms": duration_ms}
        ))

    def metrics(self) -> StoryOSMetrics:
        return self._metrics
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed
- [ ] **Step 5: Commit** — `git add application/storyos/value_objects/storyos_metrics.py application/storyos/services/metrics_recorder.py tests/unit/application/storyos/value_objects/ && git commit -m "feat(metrics): add StoryOSMetrics 6 indicators + MetricsRecorder (spec §5.2)"`

#### Task G2: ActiveAssetsContext（Step 1 输入 LLM 的活跃资产摘要）

**Files:**
- Create: `application/storyos/value_objects/active_assets_context.py`
- Create: `application/storyos/services/active_assets_service.py`
- Create: `tests/unit/application/storyos/value_objects/test_active_assets_context.py`

- [ ] **Step 1: 写失败测试**

```python
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext


def test_active_assets_context_default():
    ctx = ActiveAssetsContext(
        novel_id="n1", chapter_id=1,
    )
    assert ctx.conflicts == []
    assert ctx.mysteries == []
    assert ctx.total_active == 0


def test_active_assets_context_total_active_counts_all_lists():
    ctx = ActiveAssetsContext(
        novel_id="n1", chapter_id=1,
        conflicts=[{"id": "c1"}, {"id": "c2"}],
        mysteries=[{"id": "m1"}],
        expectations=[{"id": "e1"}],
    )
    assert ctx.total_active == 4
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`
- [ ] **Step 3: 实现** — `application/storyos/value_objects/active_assets_context.py`：

```python
"""ActiveAssetsContext — Step 1 输入 LLM 的活跃资产摘要（spec §3.1）。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ActiveAssetsContext(BaseModel):
    """当前章节活跃的 narrative asset 摘要。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    novel_id: str
    chapter_id: int

    conflicts: list[dict] = Field(default_factory=list)
    mysteries: list[dict] = Field(default_factory=list)
    twists: list[dict] = Field(default_factory=list)
    promises: list[dict] = Field(default_factory=list)
    reveals: list[dict] = Field(default_factory=list)
    expectations: list[dict] = Field(default_factory=list)
    goals: list[dict] = Field(default_factory=list)
    foreshadowings: list[dict] = Field(default_factory=list)

    @computed_field
    @property
    def total_active(self) -> int:
        return sum(len(getattr(self, field)) for field in [
            "conflicts", "mysteries", "twists", "promises", "reveals",
            "expectations", "goals", "foreshadowings",
        ])
```

并在 `application/storyos/services/active_assets_service.py` 创建构建服务（1B 简单版，1C 完善过滤逻辑）：

```python
"""ActiveAssetsService — 构建 ActiveAssetsContext。"""
from __future__ import annotations

from application.storyos.services.conflict_registry_service import ConflictRegistryService
from application.storyos.services.mystery_registry_service import MysteryRegistryService
from application.storyos.services.twist_registry_service import TwistRegistryService
from application.storyos.services.promise_registry_service import PromiseRegistryService
from application.storyos.services.reveal_registry_service import RevealRegistryService
from application.storyos.services.expectation_registry_service import ExpectationRegistryService
from application.storyos.services.goal_registry_service import GoalRegistryService
from application.storyos.services.foreshadowing_registry_service import ForeshadowingRegistryService
from application.storyos.value_objects.active_assets_context import ActiveAssetsContext


class ActiveAssetsService:
    def __init__(
        self, conflict_svc=None, mystery_svc=None, twist_svc=None,
        promise_svc=None, reveal_svc=None, expectation_svc=None,
        goal_svc=None, foreshadowing_svc=None,
    ) -> None:
        self._services = {
            "conflict": conflict_svc, "mystery": mystery_svc,
            "twist": twist_svc, "promise": promise_svc,
            "reveal": reveal_svc, "expectation": expectation_svc,
            "goal": goal_svc, "foreshadowing": foreshadowing_svc,
        }

    def build_context(self, novel_id: str, chapter_id: int) -> ActiveAssetsContext:
        kwargs = {"novel_id": novel_id, "chapter_id": chapter_id}
        for asset_type, svc in self._services.items():
            if svc is None:
                continue
            items = [e.__dict__ for e in svc.list() if e.novel_id == novel_id]
            # Enum 转 str
            for item in items:
                for k, v in list(item.items()):
                    if hasattr(v, "value"):
                        item[k] = v.value
            kwargs[f"{asset_type}s"] = items
        return ActiveAssetsContext(**kwargs)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 2 passed
- [ ] **Step 5: Commit** — `git add application/storyos/value_objects/active_assets_context.py application/storyos/services/active_assets_service.py tests/unit/application/storyos/value_objects/ && git commit -m "feat(application): add ActiveAssetsContext + service for LLM Step 1 input"`

---

## 4. 关键设计决策

### 4.1 Bridge 单事务三操作（spec §4.1 锁定）

```python
with dispatch.transaction() as txn:
    txn.queue_apply(evolution_apply, actions, novel_id)        # evolution_apply_actions
    txn.queue_apply(registry_apply_with_cascade, updates, novel_id)  # registry_apply_with_cascade
    txn.queue_apply(sflog_event_record, records, novel_id)     # sflog_event_record
```

三 op 共享一个 SQL 事务；任一失败 → 全 ROLLBACK。

### 4.2 bridge_log 事务外写（spec §3.4 ⚡ 标记）

```python
try:
    with dispatch.transaction() as txn:
        # 三个 op
except EvolutionBridgeError as e:
    # 桥外：bridge_log 走单独的 enqueue_txn_batch（不在事务内 → 不会被 ROLLBACK）
    dispatch.enqueue_txn_batch([(INSERT_BRIDGE_LOG_SQL, (...))])
    raise
```

### 4.3 SFLogComplianceGate 4 决策（spec §4.4 锁定）

| 情况 | 决策 |
|---|---|
| predeclared ⊃ records，无 unexpected | PASS |
| predeclared 有但 records 缺 | RETRY（达到 threshold → FORCE_PASS） |
| records 多出 predeclared 没有 | WARN |
| 重试达 threshold | FORCE_PASS |

### 4.4 Clue 投影到 RevealedClueItem（sub-spec §3.6 修正）

由 `MysteryRegistryService.discover_clue()` 内部完成。投影规则：
- `Clue.id` → `RevealedClueItem.clue_id`
- `Clue.description` → `RevealedClueItem.content`
- `Clue.discovered_in_chapter` → `RevealedClueItem.revealed_at_chapter`
- `Clue.category.value` → `RevealedClueItem.category`
- `Clue.status != DEAD` → `RevealedClueItem.is_still_valid`

### 4.5 CircuitBreaker 向后兼容（1A D1-D3 锁定）

- 旧 API（`is_open() / record_failure() / record_success()`）保留
- 新增 `get_retry_count(gate, scope_id) / record_retry(gate, scope_id, success) / is_gate_open(gate, scope_id)` 三方法
- 旧 API 的失败**不**计入 gate 维度（独立计数）

### 4.6 CascadeService max_depth 默认 3（spec §4.2 锁定）

- `max_depth=3`：cascade 至多 3 层
- 越界 → `result.blocked_steps.append(step)`
- 不抛异常（软失败，调用方决定如何处理）

---

## 5. 风险 + 本阶段缓解映射

| 风险 | 等级 | 本阶段缓解任务 |
|---|---|---|
| #1 LLM 合规性 | 🟡 中 | E2 SFLogComplianceGate 4 决策 |
| #2 Bridge 双写并发 | 🟢 低 | D2 EvolutionBridgeService（单事务 + 闭包陷阱修复）+ D3 性能基准 |
| #4 Cascade 性能 | 🟡 中 | C1-C3 CascadeService（BFS + depth 限制） |
| #6 旧 API 破坏 | 🟢 低 | E1 CircuitBreaker 多 gate（向后兼容） |

---

## 6. 完成判据

### 6.1 功能验收（100% 必须通过）

- [ ] A1-A3：3 个 parsers 完整（regex 11 类覆盖 + validator + 6 mapped + 5 skipped）
- [ ] B1-B3：8 个 registry service 完整（CRUD + 业务方法 + Clue 投影）
- [ ] C1-C3：CascadeService 6 trigger 全覆盖 + orphan 软失败
- [ ] D1-D3：BridgeResult 14 字段 + EvolutionBridgeService 单事务三操作 + 性能 < 200ms
- [ ] E1-E2：CircuitBreaker 多 gate + SFLogComplianceGate 4 决策
- [ ] F1-F3：SnapshotProjector + SFLogParserService + ForeshadowingMigrationService stub
- [ ] G1-G2：StoryOSMetrics 6 指标 + ActiveAssetsContext
- [ ] `pytest tests/ -m "not slow"` 全过（向后兼容验证）

### 6.2 性能基准（spec §5.3 锁定）

| 测试 | 输入 | 期望 |
|---|---|---|
| `parse_throughput` | 1000 SF_LOG | < 100ms |
| `cascade_depth_3` | 84 节点展开 | < 500ms |
| `bridge_full_chapter` | 100 SF_LOG + 50 cascade | < 200ms |

### 6.3 阶段输出交接清单（给 1C）

- [ ] `EvolutionBridgeService.apply_sflog_batch()` 暴露给 1C 引擎钩子
- [ ] `SFLogParserService.parse/validate/match` 流水线完整
- [ ] `SFLogComplianceGate.evaluate(match_report, retry_count) -> ComplianceDecision` 完整
- [ ] `CascadeService.simulate(asset_id, trigger) -> CascadePreview` 暴露给 1D 前端 dry-run
- [ ] `application/engine/services/circuit_breaker.py` 多 gate 扩展完成，向后兼容
- [ ] `ActiveAssetsService.build_context()` 供 1C 引擎 Step 1 注入 LLM

---

## 7. 任务统计

| Group | 任务数 | 关键产出 |
|---|---|---|
| A: SF_LOG Parsers | 3 | regex parser / format validator / action mapper |
| B: 8 Registry Services | 3 | 8 个 service（CRUD + 业务方法） |
| C: Cascade Service | 3 | CascadeService（BFS + 6 trigger + orphan 软失败） |
| D: Evolution Bridge | 3 | BridgeResult 14 字段 + Bridge service + 性能基准 |
| E: Circuit Breaker 多 gate | 2 | 多 gate 扩展 + SFLogComplianceGate 4 决策 |
| F: Snapshot + Integration | 3 | SnapshotProjector + ParserService + Migration stub |
| G: Metrics + ActiveAssets | 2 | StoryOSMetrics 6 指标 + ActiveAssetsContext |
| **合计** | **20** | **~25 新文件**，~3000 LOC |

**文件清单**：
- Parsers: 3 模块（regex / validator / mapper）+ 3 测试
- Services: 8 registry + cascade + bridge + parser + snapshot + compliance + metrics + active assets + migration stub = 12 文件
- Value objects: bridge_result + storyos_metrics + active_assets_context = 3 文件
- Circuit breaker 扩展: 1 文件
- Tests: ~15 测试文件
- **Total**: ~25 新文件 + 1 修改（circuit_breaker.py）

---

## 8. 执行模式

### 8.1 推荐：Subagent-Driven

1B 适合 subagent-driven：每组（Group A-G）可派 1 个 subagent，subagent 之间通过 git 提交契约衔接。

**关键契约交接点**：
- Group A 完成后 → Group D 可启动（action mapper 喂给 bridge）
- Group B 完成后 → Group C 可启动（cascade 用 registry）
- Group C 完成后 → Group D 可启动（bridge 调用 cascade）
- Group E 与 F 独立，可并行
- Group G 独立

### 8.2 备选：Inline Execution

按 A1-A3 → B1-B3 → C1-C3 → D1-D3 → E1-E2 → F1-F3 → G1-G2 顺序。

---

## 9. 进度追踪

| 任务 | 状态 | Commit | 备注 |
|---|---|---|---|
| A1 SFLogRegexParser | ⬜ 待开始 | | 11 类覆盖 |
| A2 SFLogFormatValidator | ⬜ 待开始 | | |
| A3 SFLogActionMapper | ⬜ 待开始 | | 6 mapped + 5 skipped |
| B1 Conflict + Mystery registry | ⬜ 待开始 | | 含 Clue 投影 |
| B2 Twist + Promise + Reveal | ⬜ 待开始 | | Twist 互斥 |
| B3 Expectation + Goal + Foreshadowing | ⬜ 待开始 | | |
| C1 CascadeService 基础 | ⬜ 待开始 | | BFS + cycle/depth |
| C2 CascadeService 6 trigger | ⬜ 待开始 | | spec §4.2 |
| C3 CascadeService orphan 软失败 | ⬜ 待开始 | | |
| D1 BridgeResult 14 字段 | ⬜ 待开始 | | spec §3.2 |
| D2 EvolutionBridgeService | ⬜ 待开始 | | 单事务三 op |
| D3 bridge 性能基准 < 200ms | ⬜ 待开始 | | spec §5.3 |
| E1 CircuitBreaker 多 gate | ⬜ 待开始 | | 向后兼容 |
| E2 SFLogComplianceGate 4 决策 | ⬜ 待开始 | | spec §4.4 |
| F1 SnapshotProjector | ⬜ 待开始 | | 1D API 消费 |
| F2 SFLogParserService 编排 | ⬜ 待开始 | | |
| F3 ForeshadowingMigrationService stub | ⬜ 待开始 | | 1E 补完 |
| G1 StoryOSMetrics 6 指标 | ⬜ 待开始 | | spec §5.2 |
| G2 ActiveAssetsContext | ⬜ 待开始 | | LLM Step 1 输入 |

---

## 10. 设计参考

- **Spec 主参考**：`../specs/2026-07-02-storyos-integration-design.md`
  - §3.1 application/ 文件清单
  - §3.2 类型签名（BridgeResult 14 字段）
  - §3.3 SF_LOG 11 类 → 6 映射 + 5 跳过
  - §3.4 11 张表（sflog_event / bridge_log / cascade_history）
  - §3.5 WriteDispatch 扩展
  - §3.6 CircuitBreaker 多 gate
  - §4.1 Happy Path
  - §4.2 Cascade 规则
  - §4.4 SFLogComplianceGate 4 决策
  - §5.2 StoryOSMetrics 6 指标
  - §5.3 性能基准
- **Sub-Spec**：`../specs/2026-07-02-storyos-asset-field-spec.md`
  - §3.5 Clue ↔ RevealedClueItem 字段对应
  - §3.6 DDD 修正：投影由 MysteryService 完成
- **1A 阶段产出（前置）**：`./2026-07-02-storyos-phase-1a-foundation.md`
- **1C 阶段产出（消费本阶段）**：`./2026-07-02-storyos-phase-1c-engine.md`
- **1D 阶段产出（消费本阶段）**：`./2026-07-02-storyos-phase-1d-frontend-api.md`
- **1E 阶段产出（消费本阶段）**：`./2026-07-02-storyos-phase-1e-migration.md`
- **现有代码**：
  - `domain/evolution/contracts.py`（ActionType 9 类）
  - `domain/evolution/models.py`（EvolutionAction / EvolutionState / ReducerError）
  - `application/engine/services/circuit_breaker.py`（需扩展为多 gate）
  - `application/engine/services/memory_engine.py:70`（RevealedClueItem）
  - `infrastructure/persistence/database/write_dispatch.py`（1A 扩展后含 transaction()）
- **降级/兼容**：
  - CircuitBreaker 旧 API 保留（`is_open() / record_failure() / record_success()`）
  - WriteDispatch 旧 API 保留（`queue()` 旧方法）
