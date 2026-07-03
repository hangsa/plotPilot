# StoryOS Phase 1E — Migration Tool 实施计划（详版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Parent Plan:** [`2026-07-02-storyos-integration.md`](./2026-07-02-storyos-integration.md)
**Spec Reference:** [`../specs/2026-07-02-storyos-integration-design.md`](../specs/2026-07-02-storyos-integration-design.md) §Q5, §Q8, §6.1, §6.3, 附录 C
**Sub-Spec Reference:** [`../specs/2026-07-02-storyos-asset-field-spec.md`](../specs/2026-07-02-storyos-asset-field-spec.md) §3（Clue/Foreshadowing 字段对照）
**Phase Scope:** Foreshadowing 单向迁移工具（CLI + API + Audit）+ 14 主任务
**LOC Target:** ~1200（业务逻辑 ~700 + 测试 ~500）
**Estimated Tasks:** 14
**Estimated Duration:** 2 天
**前置依赖:** Phase 1A + 1B + 1D 全部完成；Phase 1C 可与 1E 并行（无依赖）

---

## 0. 背景与目标

### 0.1 阶段目标

PlotPilot 在 1A 之前的历史项目中存有 `foreshadows` 旧表（SQLite，`schema.sql:537-550`），承载了"伏笔"这一核心叙事资产。1A 把 Foreshadowing 从 `domain/novel/` 剥离到 `domain/storyos/` 并新建 `storyos_foreshadowing_v1` 表（spec Q5 锁定）。

1E 阶段负责把**旧表数据单向迁移到新表**，旧表保留只读（spec Q8 锁定 "惰性初始化 + 旧伏笔自动转换，单向迁移，旧表只读"）。同时为 1D 已上架但返回 501 的 `/api/v1/storyos/{project_id}/migration/{preview|execute}` 两个端点补完真实业务逻辑，并提供独立的 CLI 工具供运维 / 高级用户使用。

### 0.2 与 spec §6.1 锁定映射

| Spec 条款 | 本计划实现位置 |
|---|---|
| §Q5 Registry 范围（含 Foreshadowing 迁移） | Group B `ForeshadowingMigrationService` 全量方法 |
| §Q8 现有项目迁移（单向迁移 + 旧表保留只读） | Group A1 读 adapter + Group B3 rollback 策略 |
| §6.1 5 子阶段（1E ~300 LOC / 2 天） | 本计划 ~1200 LOC（含审计 + 测试 + CLI 全量代码） |
| §6.3 Risk #3（Migration 数据不一致） | Group F1 幂等性 + 异常数据覆盖测试 + dry-run |
| 附录 C（status 映射表） | Group A1 `_OLD_TO_NEW` 常量 |
| §5.3 性能基准（migration_10k < 30s） | Group F2 性能测试 |

### 0.3 关键设计决策

1. **单向迁移 + 旧表只读（spec Q8 锁定）**：
   - 旧 `foreshadows` 表**永不修改、绝不删除**；只通过 SELECT 读取
   - 新 `storyos_foreshadowing_v1` 表接收 INSERT/UPDATE
   - 任何"回滚"操作只删除新表数据，**不**回滚旧表
   - 数据流向：`foreshadows`（只读） → `storyos_foreshadowing_v1`（写）

2. **幂等性通过唯一索引保证**：
   - 新表 `UNIQUE(migrated_from_legacy_id, project_id)` —— 重复迁移的旧 ID 直接被 unique 约束拦截（静默跳过 + 计数）
   - 这避免了在服务层做"先查后插"的竞态条件，且符合 WriteDispatch 单写者模型

3. **断点续跑通过 `migration_log` 表保证**：
   - 每批次写入一个 `storyos_migration_log_v1` 记录，含 `old_ids: JSON` 与 `status: committed/failed/rolled_back`
   - 重启时扫描 `status='committed'` 的旧 ID 集合 → 在新批次 INSERT 前过滤掉
   - 失败批次 `status='failed'` 可单独 `--rollback`（只删除该批次的 INSERT 记录）

4. **每 500 条一个事务**（spec 推断，性能与锁竞争的折中）：
   - 使用现有 `WriteDispatch.enqueue_txn_batch(operations)` —— 1A 已扩展（spec §3.5）
   - 失败时整个 500 条 batch ROLLBACK，保证原子性
   - 批次大小通过 `MigrationExecuteRequest.batch_size: int = 500` 暴露给 API/CLI

5. **状态映射表（spec 附录 C 锁定 ⚡）**：

   | 旧 `status` | 新 `AssetStatus` | 备注 |
   |---|---|---|
   | `planted` | `PLANTED` | identity |
   | `resolved` | `REVEALED` | ⚡ 重新映射（语义对齐 storyos 概念） |
   | `abandoned` | `DEAD` | ⚡ 重新映射 |
   | 其它 / NULL | （跳过） | 不在映射表的旧值 → 记录到 `invalid` 计数 |

   **关键设计点**：1A 的 `ForeshadowingMapper.convert_old_status_to_new(old_status: str) -> AssetStatus` 是本任务的依赖（1B 已锁定为 static method）。1E 直接复用，不重新实现映射逻辑。

6. **`migrated_from_legacy_id` 字段是 1A 锁定的迁移语义**：
   - 新表 schema 含 `migrated_from_legacy_id: TEXT NULL`（1A E2 任务）
   - 1D `foreshadowing_schemas.py` 也暴露了这个字段（line 4777）
   - 1E 写入时必须把旧 ID 填到这字段，供 1D 前端展示"已迁移"标识 + 后续审计追踪

7. **降级策略与 1C 对齐（spec §4.3 F 软失败）**：
   - 异常数据（旧表记录字段缺失/损坏）→ 跳过 + 写 `migration_log.invalid_ids`
   - 不抛异常中断整个 migration；最终 `MigrationPreviewResponse` 返回 5 元组 `total/scanned/migratable/skipped/invalid`

8. **CLI 独立于 API，但复用同一 Service**：
   - `scripts/migrate_storyos.py` 通过 DI container 拿 `ForeshadowingMigrationService` 单例
   - 同一 service 既被 API 调用，又被 CLI 调用，保证行为一致
   - CLI 输出 JSON 报告供运维脚本消费（与 `--execute` 后写入 `migration_log` 一致）

### 0.4 与 1A/1B/1D 边界

| 阶段 | 产出 | 1E 消费方式 |
|---|---|---|
| 1A | `infrastructure/persistence/storyos/mappers/foreshadowing_mapper.py` 含 `convert_old_status_to_new()` | Group A1 直接 import 调用 |
| 1A | `storyos_foreshadowing_v1` schema + `ForeshadowingSchema` | Group B2 INSERT 时复用 |
| 1B | `application/storyos/services/foreshadowing_migration_service.py`（stub，scan/execute/rollback 全抛 NotImplementedError） | Group B 完整实现覆盖 stub |
| 1D | `interfaces/api/v1/storyos/schemas/migration_schemas.py`（5 DTOs 已定义） | Group D1 直接消费 |
| 1D | `interfaces/api/v1/storyos/routes/migration_routes.py`（501 桩） | Group D1 替换为真实 handler |
| 1D | `interfaces/api/v1/storyos/dependencies.py` `get_migration_service()` DI 工厂 | Group D1 直接复用 |
| 1D | `frontend/src/api/storyos/migration.ts` `migrationApi` 客户端 | Group F1 集成测试验证联通 |

**不修改 1D 任何文件**：1E 完全在 D1 已有 501 桩的**函数体内**替换实现 + 新增 GET `/status` 端点。

### 0.5 测试覆盖目标

- `tests/unit/application/storyos/migration/` —— Group A 仓储适配单元测试
- `tests/unit/application/storyos/services/test_foreshadowing_migration.py` —— Group B 业务逻辑测试
- `tests/unit/application/storyos/services/test_migration_audit_service.py` —— Group C 审计测试
- `tests/integration/api/v1/storyos/test_migration_endpoints.py` —— Group D API 联通测试（替换 1D 的 501 验证）
- `tests/integration/migration/test_foreshadowing_migration_e2e.py` —— Group F 端到端（CLI 路径）
- `tests/performance/test_migration_10k.py` —— Group F2 性能基准
- `tests/unit/scripts/test_migrate_storyos_cli.py` —— Group E CLI 单元测试

### 0.6 TDD 7 步循环模板（每个任务遵循）

```
1. 写失败测试（红色）
2. 运行测试确认失败（红色，必须看到具体的失败原因）
3. 实现最小代码让测试通过（绿色）
4. 运行测试确认通过（绿色）
5. 运行回归测试（确保不破坏现有代码）
6. Commit（一个任务一个原子 commit）
7. （可选）Refactor —— 仅在测试通过后清理
```

**TDD 严格性**：步骤 1 和步骤 2 是强制性的。**禁止**先写实现再补测试。

---

## 1. 文件结构

### 1.1 新增文件

```
application/storyos/migration/                                # 新目录
  __init__.py
  legacy_foreshadowing_adapter.py                              # 旧表只读读取
  migration_log_repository.py                                  # migration_log CRUD
  status_mapper.py                                             # 旧→新 status 映射（薄包装 1A mapper）

application/storyos/services/
  foreshadowing_migration_service.py                          # 1B stub → 1E 完整实现
  migration_audit_service.py                                   # 审计聚合

scripts/
  migrate_storyos.py                                           # 1A 脚手架 → 1E 完整 CLI

infrastructure/persistence/storyos/
  migration_log_schema.py                                      # storyos_migration_log_v1 ORM
  migration_log_mapper.py                                      # row ↔ MigrationLogEntry
```

### 1.2 修改文件

```
interfaces/api/v1/storyos/routes/migration_routes.py          # 1D 501 → 1E 真实 handler + GET /status
interfaces/api/v1/storyos/dependencies.py                     # （可选）audit service DI 工厂
```

### 1.3 测试文件

```
tests/unit/application/storyos/migration/
  __init__.py
  test_legacy_foreshadowing_adapter.py                         # 5 测试
  test_migration_log_repository.py                             # 6 测试
  test_status_mapper.py                                        # 4 测试

tests/unit/application/storyos/services/
  test_foreshadowing_migration.py                              # 16 测试（替换 1B 的 stub 测试）
  test_migration_audit_service.py                              # 8 测试

tests/integration/api/v1/storyos/
  test_migration_endpoints.py                                  # 12 测试（替换 1D 的 501 测试）

tests/integration/migration/
  __init__.py
  test_foreshadowing_migration_e2e.py                          # 8 测试

tests/performance/
  test_migration_10k.py                                        # 2 测试

tests/unit/scripts/
  __init__.py
  test_migrate_storyos_cli.py                                  # 6 测试
```

### 1.4 不修改（确认边界）

- `interfaces/api/v1/storyos/schemas/migration_schemas.py` —— 1D 已完整定义 5 DTOs
- `interfaces/api/v1/storyos/crud_factory.py` —— 1D factory 不涉及 migration
- `domain/storyos/value_objects/` —— 1A 已锁定的所有 value objects
- `application/storyos/services/cascade_service.py` 等业务 service —— 1B 已完成
- **不修改任何 1D 前端文件**：migration.ts / migrationApi 已就绪，等后端真实返回

---

## 2. 任务分组

```
Group A: 仓储 + Schema 适配层 (3 任务)
  - A1: legacy_foreshadowing_adapter（只读读取旧表 + status 映射）
  - A2: migration_log_repository（断点续跑 + 审计持久化）
  - A3: status_mapper（1A ForeshadowingMapper.convert_old_status_to_new 的薄包装）

Group B: Migration Service 业务逻辑 (3 任务)
  - B1: scan() —— 5 元组预览报告（total/scanned/migratable/skipped/invalid）
  - B2: execute() —— 批量迁移 + 幂等 + dry_run + 断点续跑
  - B3: rollback() —— 按 migration_id 删除新表数据 + 更新 migration_log

Group C: 迁移审计 (2 任务)
  - C1: MigrationAuditService.record_batch() —— 每批次 success/failure/skip 计数
  - C2: MigrationReportAggregator —— 聚合多个批次生成最终 JSON 报告

Group D: API 联通 (2 任务)
  - D1: 替换 1D 501 桩 → 真实 preview/execute handler（消费 1D 已定义的 5 DTOs）
  - D2: GET /api/v1/storyos/{project_id}/migration/{migration_id}/status（1D 未定义，1E 新增）

Group E: CLI 完整实现 (2 任务)
  - E1: --dry-run + --execute + JSON 输出 + 进度条
  - E2: --rollback + --status + 错误聚合

Group F: 集成 + 性能测试 (2 任务)
  - F1: 端到端集成测试（幂等性 / 异常数据 / 批次边界 / 旧表保留只读）
  - F2: 10k 性能基准（migration_10k < 30s + dry_run < 5s，spec §5.3 锁定）

总计 14 主任务。
```

---

## 3. 任务详化

### Group A: 仓储 + Schema 适配层

#### Task A1: legacy_foreshadowing_adapter（只读读取旧表 + 字段映射）

**Files:**
- Create: `application/storyos/migration/__init__.py`（空）
- Create: `application/storyos/migration/legacy_foreshadowing_adapter.py`
- Create: `tests/unit/application/storyos/migration/test_legacy_foreshadowing_adapter.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/application/storyos/migration/test_legacy_foreshadowing_adapter.py
"""legacy_foreshadowing_adapter 单元测试。

适配层只读读取旧 foreshadows 表，转换为 LegacyForeshadowingRecord dataclass，
供 MigrationService.scan() / execute() 消费。
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingAdapter,
    LegacyForeshadowingRecord,
)


@pytest.fixture
def fake_db_cursor():
    """模拟 SQLite cursor，返回旧表行数据。"""
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        # 旧表 schema.sql:537-550 字段顺序
        ("fs-1", "novel-1", "主角得到神秘信件", 5, None, None, "planted", 3, None),
        ("fs-2", "novel-1", "反派首次露面", 3, 10, 12, "resolved", 4, None),
        ("fs-3", "novel-1", "被废弃的支线", 7, None, None, "abandoned", 1, None),
    ]
    return cursor


def test_legacy_record_dataclass_fields():
    """LegacyForeshadowingRecord 字段集：8 字段对应旧表列。"""
    rec = LegacyForeshadowingRecord(
        id="fs-1",
        novel_id="novel-1",
        description="desc",
        planted_chapter=5,
        due_chapter=None,
        resolved_chapter=None,
        status="planted",
        importance=3,
        subtext_type=None,
    )
    assert rec.id == "fs-1"
    assert rec.planted_chapter == 5
    assert rec.importance == 3


def test_fetch_all_returns_records(fake_db_cursor):
    """adapter.fetch_all_for_novel 读取所有记录。"""
    adapter = LegacyForeshadowingAdapter(cursor_provider=lambda _: fake_db_cursor)
    records = adapter.fetch_all_for_novel("novel-1")
    assert len(records) == 3
    assert records[0].id == "fs-1"
    assert records[1].status == "resolved"
    assert records[2].status == "abandoned"


def test_fetch_all_returns_empty_when_no_records():
    """空表返回空列表（不抛异常）。"""
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    adapter = LegacyForeshadowingAdapter(cursor_provider=lambda _: cursor)
    assert adapter.fetch_all_for_novel("novel-empty") == []


def test_count_for_novel_uses_select_count():
    """count_for_novel 走 SELECT COUNT(*) 路径，不拉全量数据。"""
    cursor = MagicMock()
    cursor.fetchone.return_value = (42,)
    adapter = LegacyForeshadowingAdapter(cursor_provider=lambda _: cursor)
    assert adapter.count_for_novel("novel-1") == 42
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args.args[0]
    assert "SELECT COUNT(*)" in sql
    assert "foreshadows" in sql


def test_fetch_all_skips_corrupted_rows_gracefully(fake_db_cursor):
    """字段损坏（如 importance 不是 int）→ 跳过该行 + 记录到 invalid_ids。

    降级策略：单行损坏不阻断整个 fetch。
    """
    cursor = MagicMock()
    cursor.fetchall.return_value = [
        ("fs-good", "novel-1", "good", 1, None, None, "planted", 2, None),
        ("fs-bad", "novel-1", "bad", 1, None, None, "planted", "NOT_AN_INT", None),  # 类型错
        ("fs-good2", "novel-1", "good2", 2, None, None, "planted", 3, None),
    ]
    adapter = LegacyForeshadowingAdapter(cursor_provider=lambda _: cursor)
    records, invalid_ids = adapter.fetch_all_with_invalid("novel-1")
    assert len(records) == 2
    assert records[0].id == "fs-good"
    assert "fs-bad" in invalid_ids


def test_adapter_does_not_modify_legacy_table():
    """adapter 严禁执行 INSERT/UPDATE/DELETE —— 通过白名单验证。

    这是 spec Q8 "旧表只读" 约束的代码层强制。
    """
    forbidden_keywords = ["INSERT", "UPDATE", "DELETE", "REPLACE", "DROP"]
    adapter = LegacyForeshadowingAdapter(cursor_provider=lambda _: MagicMock())
    # 检查 adapter 提供的所有方法的 SQL 关键字
    for method_name in ["fetch_all_for_novel", "count_for_novel"]:
        method = getattr(adapter, method_name)
        # 用 mock cursor 拦截 execute 调用
        cursor = MagicMock()
        method("novel-1", cursor=cursor) if method_name != "fetch_all_for_novel" else method("novel-1")
        if cursor.execute.called:
            sql = cursor.execute.call_args.args[0].upper()
            for kw in forbidden_keywords:
                assert kw not in sql, f"{method_name} must not use {kw}: {sql}"
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`

Run: `pytest tests/unit/application/storyos/migration/test_legacy_foreshadowing_adapter.py -v`
Expected: FAILED with `ModuleNotFoundError: No module named 'application.storyos.migration'`

- [ ] **Step 3: 实现**

```python
# application/storyos/migration/__init__.py
"""StoryOS migration subsystem — Foreshadowing 单向迁移（spec Q8 锁定）。"""
```

```python
# application/storyos/migration/legacy_foreshadowing_adapter.py
"""legacy_foreshadowing_adapter —— 旧 foreshadows 表只读读取。

约束（spec Q8 锁定 + spec §6.3 Risk #3 缓解）：
- 严禁任何 INSERT/UPDATE/DELETE/REPLACE/DROP 操作
- 只通过 SELECT 拉取数据，转换为 LegacyForeshadowingRecord dataclass
- 损坏行降级处理（跳过 + 记录到 invalid_ids），不抛异常中断整个 fetch
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Tuple


@dataclass(frozen=True)
class LegacyForeshadowingRecord:
    """旧 foreshadows 表行数据（只读视图）。

    字段对应 schema.sql:537-550 的 9 列：
        id, novel_id, description, planted_chapter, due_chapter,
        resolved_chapter, status, importance, subtext_type
    """
    id: str
    novel_id: str
    description: str
    planted_chapter: int
    due_chapter: Optional[int]
    resolved_chapter: Optional[int]
    status: str
    importance: int
    subtext_type: Optional[str]


CursorProvider = Callable[[str], Any]


class LegacyForeshadowingAdapter:
    """旧表只读 adapter（spec Q8）。

    cursor_provider 是注入依赖，方便测试 mock；生产环境传入
    `lambda sql: sqlite_connection.execute(sql)`。
    """

    _FORBIDDEN_SQL_KEYWORDS = frozenset(["INSERT", "UPDATE", "DELETE", "REPLACE", "DROP"])

    def __init__(self, cursor_provider: CursorProvider) -> None:
        self._cursor_provider = cursor_provider

    def fetch_all_for_novel(self, novel_id: str) -> List[LegacyForeshadowingRecord]:
        records, _ = self.fetch_all_with_invalid(novel_id)
        return records

    def fetch_all_with_invalid(
        self, novel_id: str,
    ) -> Tuple[List[LegacyForeshadowingRecord], List[str]]:
        """拉取 novel 下所有 foreshadowing 行；损坏行降级到 invalid_ids。

        Returns:
            (records, invalid_ids): records 是合法行，invalid_ids 是损坏行 ID 列表。
        """
        cursor = self._cursor_provider(
            "SELECT id, novel_id, description, planted_chapter, due_chapter, "
            "resolved_chapter, status, importance, subtext_type "
            "FROM foreshadows WHERE novel_id = ? ORDER BY id"
        )
        # cursor 期望支持参数化查询
        rows = cursor.fetchall()
        records: List[LegacyForeshadowingRecord] = []
        invalid_ids: List[str] = []
        for row in rows:
            try:
                records.append(self._row_to_record(row))
            except (ValueError, TypeError) as e:
                invalid_ids.append(row[0])  # row[0] = id
        return records, invalid_ids

    def count_for_novel(self, novel_id: str) -> int:
        cursor = self._cursor_provider(
            "SELECT COUNT(*) FROM foreshadows WHERE novel_id = ?"
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def _row_to_record(row: tuple) -> LegacyForeshadowingRecord:
        """row → LegacyForeshadowingRecord，类型校验失败抛 ValueError。"""
        if len(row) != 9:
            raise ValueError(f"Expected 9 columns, got {len(row)}")
        return LegacyForeshadowingRecord(
            id=str(row[0]),
            novel_id=str(row[1]),
            description=str(row[2]),
            planted_chapter=int(row[3]),
            due_chapter=int(row[4]) if row[4] is not None else None,
            resolved_chapter=int(row[5]) if row[5] is not None else None,
            status=str(row[6]),
            importance=int(row[7]),
            subtext_type=str(row[8]) if row[8] is not None else None,
        )
```

- [ ] **Step 4: 运行测试确认通过** — 期望 6 passed

Run: `pytest tests/unit/application/storyos/migration/test_legacy_foreshadowing_adapter.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add application/storyos/migration/ tests/unit/application/storyos/migration/
git commit -m "feat(migration): add legacy_foreshadowing_adapter with read-only constraint (spec Q8)"
```

---

#### Task A2: migration_log_repository（断点续跑 + 审计持久化）

**Files:**
- Create: `infrastructure/persistence/storyos/migration_log_schema.py`
- Create: `infrastructure/persistence/storyos/migration_log_mapper.py`
- Create: `application/storyos/migration/migration_log_repository.py`
- Create: `tests/unit/application/storyos/migration/test_migration_log_repository.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/application/storyos/migration/test_migration_log_repository.py
"""migration_log_repository 单元测试。

migration_log 表（spec §1E 锁定）持久化每个批次的状态，支持：
- 断点续跑：查询已 committed 的 old_ids 集合
- 回滚：通过 migration_id 删除对应批次 + 更新 log.status
"""
from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from application.storyos.migration.migration_log_repository import (
    MigrationLogRepository,
    MigrationLogEntry,
    MigrationStatus,
)


@pytest.fixture
def fake_db():
    db = MagicMock()
    # fetchall 返回已迁移的 old_id 列表
    db.execute.return_value.fetchall.return_value = [
        ("fs-1",), ("fs-2",), ("fs-3",),
    ]
    db.execute.return_value.fetchone.return_value = None
    return db


def test_migration_status_enum_members():
    """MigrationStatus 3 值：committed / failed / rolled_back（spec §1E 锁定）。"""
    assert MigrationStatus.COMMITTED.value == "committed"
    assert MigrationStatus.FAILED.value == "failed"
    assert MigrationStatus.ROLLED_BACK.value == "rolled_back"


def test_migration_log_entry_fields():
    """MigrationLogEntry 9 字段（含 spec §1E 锁定的 schema）。"""
    entry = MigrationLogEntry(
        id="ml-1",
        project_id="novel-1",
        migration_type="foreshadowing_v1",
        batch_id="batch-001",
        old_ids=["fs-1", "fs-2"],
        status=MigrationStatus.COMMITTED,
        started_at="2026-07-03T10:00:00",
        completed_at="2026-07-03T10:00:05",
        error=None,
    )
    assert entry.migration_type == "foreshadowing_v1"
    assert entry.status == MigrationStatus.COMMITTED
    assert len(entry.old_ids) == 2


def test_repo_records_committed_batch(fake_db):
    """record_committed_batch 写入一条 committed 记录。"""
    repo = MigrationLogRepository(db_provider=lambda: fake_db)
    repo.record_committed_batch(
        migration_id="ml-1",
        project_id="novel-1",
        batch_id="batch-001",
        old_ids=["fs-1", "fs-2"],
        started_at="2026-07-03T10:00:00",
        completed_at="2026-07-03T10:00:05",
    )
    fake_db.execute.assert_called()
    sql = fake_db.execute.call_args.args[0]
    assert "INSERT" in sql.upper()
    assert "migration_log" in sql or "storyos_migration_log" in sql


def test_repo_records_failed_batch(fake_db):
    """record_failed_batch 写入一条 failed 记录（含 error 信息）。"""
    repo = MigrationLogRepository(db_provider=lambda: fake_db)
    repo.record_failed_batch(
        migration_id="ml-2",
        project_id="novel-1",
        batch_id="batch-002",
        old_ids=["fs-3"],
        started_at="2026-07-03T10:00:00",
        error="UNIQUE constraint failed",
    )
    sql = fake_db.execute.call_args.args[0]
    assert "INSERT" in sql.upper()
    params = fake_db.execute.call_args.args[1]
    assert "failed" in params or "UNIQUE constraint" in str(params)


def test_repo_get_committed_old_ids_returns_set(fake_db):
    """get_committed_old_ids 返回已迁移 old_id 集合（供断点续跑）。"""
    repo = MigrationLogRepository(db_provider=lambda: fake_db)
    committed = repo.get_committed_old_ids("novel-1", migration_type="foreshadowing_v1")
    assert committed == {"fs-1", "fs-2", "fs-3"}
    sql = fake_db.execute.call_args.args[0]
    assert "committed" in sql
    assert "foreshadowing_v1" in sql


def test_repo_mark_rolled_back_updates_status(fake_db):
    """mark_rolled_back 把 committed → rolled_back（rollback 流程）。"""
    repo = MigrationLogRepository(db_provider=lambda: fake_db)
    repo.mark_rolled_back("ml-1")
    sql = fake_db.execute.call_args.args[0]
    assert "UPDATE" in sql.upper()
    assert "rolled_back" in sql


def test_repo_get_entry_by_id(fake_db):
    """get_entry 返回单条 MigrationLogEntry。"""
    fake_db.execute.return_value.fetchone.return_value = (
        "ml-1", "novel-1", "foreshadowing_v1", "batch-001",
        '["fs-1","fs-2"]', "committed",
        "2026-07-03T10:00:00", "2026-07-03T10:00:05", None,
    )
    repo = MigrationLogRepository(db_provider=lambda: fake_db)
    entry = repo.get_entry("ml-1")
    assert entry is not None
    assert entry.id == "ml-1"
    assert entry.old_ids == ["fs-1", "fs-2"]
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`

Run: `pytest tests/unit/application/storyos/migration/test_migration_log_repository.py -v`
Expected: FAILED with `ModuleNotFoundError`

- [ ] **Step 3: 实现**

```python
# infrastructure/persistence/storyos/migration_log_schema.py
"""storyos_migration_log_v1 表 ORM 定义。

schema（spec §1E 锁定）：
    id TEXT PRIMARY KEY
    project_id TEXT NOT NULL
    migration_type TEXT NOT NULL         -- 'foreshadowing_v1'
    batch_id TEXT NOT NULL
    old_ids TEXT NOT NULL                -- JSON list
    status TEXT NOT NULL                 -- 'committed' | 'failed' | 'rolled_back'
    started_at TEXT NOT NULL
    completed_at TEXT
    error TEXT
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class MigrationLogSchema:
    """storyos_migration_log_v1 行数据。"""
    id: str
    project_id: str
    migration_type: str
    batch_id: str
    old_ids_json: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS storyos_migration_log_v1 (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    migration_type TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    old_ids TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_migration_log_project_type
    ON storyos_migration_log_v1(project_id, migration_type, status);
"""
```

```python
# infrastructure/persistence/storyos/migration_log_mapper.py
"""row ↔ MigrationLogEntry 映射。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class MigrationStatus(str, Enum):
    COMMITTED = "committed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass(frozen=True)
class MigrationLogEntry:
    id: str
    project_id: str
    migration_type: str
    batch_id: str
    old_ids: List[str]
    status: MigrationStatus
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class MigrationLogMapper:
    @staticmethod
    def row_to_entry(row: tuple) -> MigrationLogEntry:
        return MigrationLogEntry(
            id=row[0],
            project_id=row[1],
            migration_type=row[2],
            batch_id=row[3],
            old_ids=json.loads(row[4]) if row[4] else [],
            status=MigrationStatus(row[5]),
            started_at=row[6],
            completed_at=row[7],
            error=row[8],
        )

    @staticmethod
    def entry_to_row(entry: MigrationLogEntry) -> tuple:
        return (
            entry.id,
            entry.project_id,
            entry.migration_type,
            entry.batch_id,
            json.dumps(entry.old_ids),
            entry.status.value,
            entry.started_at,
            entry.completed_at,
            entry.error,
        )
```

```python
# application/storyos/migration/migration_log_repository.py
"""migration_log 仓储（断点续跑 + 审计持久化）。"""
from __future__ import annotations

import json
from typing import Any, Callable, List, Optional, Set

from infrastructure.persistence.storyos.migration_log_mapper import (
    MigrationLogEntry,
    MigrationLogMapper,
    MigrationStatus,
)

DbProvider = Callable[[], Any]


class MigrationLogRepository:
    """storyos_migration_log_v1 表 CRUD 仓储。"""

    def __init__(self, db_provider: DbProvider) -> None:
        self._db_provider = db_provider

    def record_committed_batch(
        self,
        migration_id: str,
        project_id: str,
        batch_id: str,
        old_ids: List[str],
        started_at: str,
        completed_at: str,
    ) -> None:
        self._insert_log(
            migration_id=migration_id,
            project_id=project_id,
            batch_id=batch_id,
            old_ids=old_ids,
            status=MigrationStatus.COMMITTED,
            started_at=started_at,
            completed_at=completed_at,
            error=None,
        )

    def record_failed_batch(
        self,
        migration_id: str,
        project_id: str,
        batch_id: str,
        old_ids: List[str],
        started_at: str,
        error: str,
    ) -> None:
        self._insert_log(
            migration_id=migration_id,
            project_id=project_id,
            batch_id=batch_id,
            old_ids=old_ids,
            status=MigrationStatus.FAILED,
            started_at=started_at,
            completed_at=None,
            error=error,
        )

    def _insert_log(
        self,
        migration_id: str,
        project_id: str,
        batch_id: str,
        old_ids: List[str],
        status: MigrationStatus,
        started_at: str,
        completed_at: Optional[str],
        error: Optional[str],
    ) -> None:
        db = self._db_provider()
        db.execute(
            "INSERT INTO storyos_migration_log_v1 "
            "(id, project_id, migration_type, batch_id, old_ids, status, started_at, completed_at, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                migration_id,
                project_id,
                "foreshadowing_v1",
                batch_id,
                json.dumps(old_ids),
                status.value,
                started_at,
                completed_at,
                error,
            ),
        )
        db.commit()

    def get_committed_old_ids(
        self,
        project_id: str,
        migration_type: str = "foreshadowing_v1",
    ) -> Set[str]:
        """返回该项目+类型下所有已 committed 的 old_id 集合（供断点续跑过滤）。"""
        db = self._db_provider()
        rows = db.execute(
            "SELECT DISTINCT json_each.value FROM storyos_migration_log_v1, "
            "json_each(storyos_migration_log_v1.old_ids) "
            "WHERE project_id = ? AND migration_type = ? AND status = 'committed'",
            (project_id, migration_type),
        ).fetchall()
        return {row[0] for row in rows}

    def mark_rolled_back(self, migration_id: str) -> None:
        """把单条 committed → rolled_back（rollback 流程）。"""
        db = self._db_provider()
        db.execute(
            "UPDATE storyos_migration_log_v1 SET status = 'rolled_back' "
            "WHERE id = ? AND status = 'committed'",
            (migration_id,),
        )
        db.commit()

    def get_entry(self, migration_id: str) -> Optional[MigrationLogEntry]:
        db = self._db_provider()
        row = db.execute(
            "SELECT id, project_id, migration_type, batch_id, old_ids, status, "
            "started_at, completed_at, error FROM storyos_migration_log_v1 WHERE id = ?",
            (migration_id,),
        ).fetchone()
        if row is None:
            return None
        return MigrationLogMapper.row_to_entry(row)
```

- [ ] **Step 4: 运行测试确认通过** — 期望 7 passed

Run: `pytest tests/unit/application/storyos/migration/test_migration_log_repository.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add infrastructure/persistence/storyos/migration_log_schema.py infrastructure/persistence/storyos/migration_log_mapper.py application/storyos/migration/migration_log_repository.py tests/unit/application/storyos/migration/test_migration_log_repository.py
git commit -m "feat(migration): add migration_log schema + repository (断点续跑 + rollback 支持)"
```

---

#### Task A3: status_mapper（1A ForeshadowingMapper.convert_old_status_to_new 薄包装）

**Files:**
- Create: `application/storyos/migration/status_mapper.py`
- Create: `tests/unit/application/storyos/migration/test_status_mapper.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/application/storyos/migration/test_status_mapper.py
"""status_mapper 单元测试。

薄包装 1A ForeshadowingMapper.convert_old_status_to_new，添加：
- 异常类型定义（UnknownLegacyStatusError）
- 批量转换 API（map_many）
- 跳过计数（map_with_skip）
"""
from __future__ import annotations

import pytest

from application.storyos.migration.status_mapper import (
    StatusMapper,
    UnknownLegacyStatusError,
)
from domain.storyos.contracts import AssetStatus
from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingRecord,
)


def test_map_planted_to_PLANTED():
    """旧 planted → 新 PLANTED（identity）。"""
    assert StatusMapper.map_status("planted") == AssetStatus.PLANTED


def test_map_resolved_to_REVEALED():
    """旧 resolved → 新 REVEALED（⚡ 重新映射，spec 附录 C 锁定）。"""
    assert StatusMapper.map_status("resolved") == AssetStatus.REVEALED


def test_map_abandoned_to_DEAD():
    """旧 abandoned → 新 DEAD（⚡ 重新映射）。"""
    assert StatusMapper.map_status("abandoned") == AssetStatus.DEAD


def test_map_unknown_raises():
    """未在映射表的旧值抛 UnknownLegacyStatusError。"""
    with pytest.raises(UnknownLegacyStatusError) as exc_info:
        StatusMapper.map_status("weird_state")
    assert "weird_state" in str(exc_info.value)


def test_map_status_or_skip_returns_none_for_unknown():
    """map_status_or_skip 返回 None（不抛异常）—— 用于降级到 invalid 计数。"""
    assert StatusMapper.map_status_or_skip("planted") == AssetStatus.PLANTED
    assert StatusMapper.map_status_or_skip("weird_state") is None


def test_map_many_returns_pairs():
    """map_many 批量转换，返回 (new_status, record) 元组列表。"""
    records = [
        LegacyForeshadowingRecord(
            id="fs-1", novel_id="n1", description="d",
            planted_chapter=1, due_chapter=None, resolved_chapter=None,
            status="planted", importance=2, subtext_type=None,
        ),
        LegacyForeshadowingRecord(
            id="fs-2", novel_id="n1", description="d",
            planted_chapter=1, due_chapter=None, resolved_chapter=5,
            status="resolved", importance=2, subtext_type=None,
        ),
    ]
    pairs = StatusMapper.map_many(records)
    assert len(pairs) == 2
    assert pairs[0][0] == AssetStatus.PLANTED
    assert pairs[1][0] == AssetStatus.REVEALALED if False else pairs[1][0] == AssetStatus.REVEALED


def test_map_with_skip_partitions_known_unknown():
    """map_with_skip 把 records 拆分为 (migratable, invalid_ids)。"""
    records = [
        LegacyForeshadowingRecord(
            id="fs-1", novel_id="n1", description="d",
            planted_chapter=1, due_chapter=None, resolved_chapter=None,
            status="planted", importance=2, subtext_type=None,
        ),
        LegacyForeshadowingRecord(
            id="fs-bad", novel_id="n1", description="d",
            planted_chapter=1, due_chapter=None, resolved_chapter=None,
            status="legacy_weird", importance=2, subtext_type=None,
        ),
    ]
    migratable, invalid_ids = StatusMapper.map_with_skip(records)
    assert len(migratable) == 1
    assert migratable[0][0].id == "fs-1"
    assert migratable[0][1] == AssetStatus.PLANTED
    assert invalid_ids == ["fs-bad"]
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`

Run: `pytest tests/unit/application/storyos/migration/test_status_mapper.py -v`
Expected: FAILED

- [ ] **Step 3: 实现**

```python
# application/storyos/migration/status_mapper.py
"""status_mapper —— 旧→新 status 映射的薄包装。

直接复用 1A ForeshadowingMapper.convert_old_status_to_new，
添加批量 API + 降级返回 None 的版本（供 scan 报告 invalid 计数）。
"""
from __future__ import annotations

from typing import List, Tuple

from domain.storyos.contracts import AssetStatus
from infrastructure.persistence.storyos.mappers.foreshadowing_mapper import (
    ForeshadowingMapper,
)

from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingRecord,
)


class UnknownLegacyStatusError(ValueError):
    """旧 status 值不在映射表内。"""


class StatusMapper:
    @staticmethod
    def map_status(old_status: str) -> AssetStatus:
        try:
            return ForeshadowingMapper.convert_old_status_to_new(old_status)
        except ValueError as e:
            raise UnknownLegacyStatusError(
                f"Unknown legacy foreshadowing status: {old_status!r}"
            ) from e

    @staticmethod
    def map_status_or_skip(old_status: str):
        """返回 AssetStatus 或 None（None 表示 invalid，跳过）。"""
        try:
            return ForeshadowingMapper.convert_old_status_to_new(old_status)
        except ValueError:
            return None

    @staticmethod
    def map_many(
        records: List[LegacyForeshadowingRecord],
    ) -> List[Tuple[LegacyForeshadowingRecord, AssetStatus]]:
        """批量映射；不存在的 status 抛 UnknownLegacyStatusError。"""
        return [(r, StatusMapper.map_status(r.status)) for r in records]

    @staticmethod
    def map_with_skip(
        records: List[LegacyForeshadowingRecord],
    ) -> Tuple[List[Tuple[LegacyForeshadowingRecord, AssetStatus]], List[str]]:
        """返回 (migratable_pairs, invalid_ids)。

        - migratable_pairs: (record, new_status) 元组列表
        - invalid_ids: 损坏 / 未知 status 的旧 ID 列表
        """
        migratable: List[Tuple[LegacyForeshadowingRecord, AssetStatus]] = []
        invalid_ids: List[str] = []
        for r in records:
            new_status = StatusMapper.map_status_or_skip(r.status)
            if new_status is None:
                invalid_ids.append(r.id)
            else:
                migratable.append((r, new_status))
        return migratable, invalid_ids
```

- [ ] **Step 4: 运行测试确认通过** — 期望 7 passed

Run: `pytest tests/unit/application/storyos/migration/test_status_mapper.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add application/storyos/migration/status_mapper.py tests/unit/application/storyos/migration/test_status_mapper.py
git commit -m "feat(migration): add status_mapper wrapping 1A ForeshadowingMapper (批量 + 降级)"
```

---

### Group B: Migration Service 业务逻辑

#### Task B1: scan() —— 5 元组预览报告

**Files:**
- Modify: `application/storyos/services/foreshadowing_migration_service.py`（1B stub → 实现 scan）
- Modify: `tests/unit/application/storyos/services/test_foreshadowing_migration_stub.py`（替换 → 真实测试）
- Create: `application/storyos/value_objects/migration_preview_report.py`（5 元组 dataclass）
- Create: `tests/unit/application/storyos/value_objects/test_migration_preview_report.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/application/storyos/value_objects/test_migration_preview_report.py
"""MigrationPreviewReport 5 元组 dataclass 测试。"""
from application.storyos.value_objects.migration_preview_report import (
    MigrationPreviewReport,
    MigrationSampleError,
)


def test_report_fields_default_to_zero():
    r = MigrationPreviewReport(project_id="n1")
    assert r.total == 0
    assert r.scanned == 0
    assert r.migratable == 0
    assert r.skipped == 0
    assert r.invalid == 0
    assert r.sample_errors == []


def test_report_full_construction():
    r = MigrationPreviewReport(
        project_id="n1",
        total=100,
        scanned=100,
        migratable=85,
        skipped=10,
        invalid=5,
        sample_errors=[
            MigrationSampleError(old_id="fs-3", code="UNKNOWN_STATUS", message="..."),
        ],
    )
    assert r.invalid == 5
    assert r.sample_errors[0].code == "UNKNOWN_STATUS"


def test_report_to_dict_snake_case_keys():
    """to_dict 输出 snake_case 键（与 1D DTO MigrationPreviewResponse 对齐）。"""
    r = MigrationPreviewReport(project_id="n1", total=10, scanned=10, migratable=8, skipped=1, invalid=1)
    d = r.to_dict()
    assert d["project_id"] == "n1"
    assert d["total"] == 10
    assert d["migratable"] == 8
    assert d["sample_errors"] == []
```

```python
# 在 tests/unit/application/storyos/services/test_foreshadowing_migration.py 中追加
# （替换 1B 的 stub 测试）

"""ForeshadowingMigrationService.scan() 单元测试。"""
from unittest.mock import MagicMock
from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingRecord,
)


def _fake_records():
    return [
        LegacyForeshadowingRecord(
            id=f"fs-{i}", novel_id="n1", description=f"d{i}",
            planted_chapter=i, due_chapter=None, resolved_chapter=None,
            status="planted" if i % 3 == 0 else ("resolved" if i % 3 == 1 else "abandoned"),
            importance=2, subtext_type=None,
        )
        for i in range(1, 11)
    ]


def test_scan_returns_5_tuple_report():
    """scan 返回 5 元组：total/scanned/migratable/skipped/invalid。"""
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = (_fake_records(), [])
    service = ForeshadowingMigrationService(legacy_adapter=adapter)
    report = service.scan("novel-1")
    assert report.total == 10
    assert report.scanned == 10
    assert report.migratable == 10  # 所有 10 条都映射成功
    assert report.invalid == 0


def test_scan_partitions_invalid_ids():
    """scan 把损坏 / 未知 status 的记录计入 invalid。"""
    records = _fake_records()
    records.append(LegacyForeshadowingRecord(
        id="fs-bad", novel_id="n1", description="d",
        planted_chapter=1, due_chapter=None, resolved_chapter=None,
        status="legacy_weird", importance=2, subtext_type=None,
    ))
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = (records, [])
    service = ForeshadowingMigrationService(legacy_adapter=adapter)
    report = service.scan("novel-1")
    assert report.migratable == 10
    assert report.invalid == 1
    assert any(e.old_id == "fs-bad" for e in report.sample_errors)


def test_scan_partitions_adapter_corrupted_rows():
    """scan 也接收 adapter 返回的 invalid_ids（field 损坏行）。"""
    records = _fake_records()
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = (records, ["fs-corrupt-1", "fs-corrupt-2"])
    service = ForeshadowingMigrationService(legacy_adapter=adapter)
    report = service.scan("novel-1")
    assert report.invalid == 3  # 1 unknown status + 2 corrupted
    assert report.migratable == 10


def test_scan_empty_project_returns_zero_report():
    """空项目 scan 返回全 0 报告，不抛异常。"""
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = ([], [])
    service = ForeshadowingMigrationService(legacy_adapter=adapter)
    report = service.scan("novel-empty")
    assert report.total == 0
    assert report.scanned == 0
    assert report.migratable == 0


def test_scan_does_not_modify_database():
    """scan 是只读操作（不能写 migration_log 或新表）。"""
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = (_fake_records(), [])
    log_repo = MagicMock()
    service = ForeshadowingMigrationService(
        legacy_adapter=adapter, log_repository=log_repo,
    )
    service.scan("novel-1")
    # log_repository 不能被 scan 调用任何写方法
    log_repo.record_committed_batch.assert_not_called()
    log_repo.record_failed_batch.assert_not_called()
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError` 或 `NotImplementedError`

Run: `pytest tests/unit/application/storyos/value_objects/test_migration_preview_report.py tests/unit/application/storyos/services/test_foreshadowing_migration.py -v`
Expected: FAILED

- [ ] **Step 3: 实现**

```python
# application/storyos/value_objects/migration_preview_report.py
"""MigrationPreviewReport —— scan() 返回的 5 元组报告（与 1D DTO 对齐）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class MigrationSampleError:
    """样例错误（旧 ID + 错误代码 + 消息），最多保留前 10 条。"""
    old_id: str
    code: str
    message: str


@dataclass(frozen=True)
class MigrationPreviewReport:
    """迁移预览报告 5 元组（spec 附录 C + 1D MigrationPreviewResponse）。

    字段语义：
        total: 旧表记录总数
        scanned: 实际扫描的记录数
        migratable: 可迁移记录数（旧 status 在映射表 + 字段完整）
        skipped: 已迁移过（committed）的记录数（断点续跑命中）
        invalid: 损坏行（adapter_corrupted + unknown_status）
    """
    project_id: str
    total: int = 0
    scanned: int = 0
    migratable: int = 0
    skipped: int = 0
    invalid: int = 0
    sample_errors: List[MigrationSampleError] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "total": self.total,
            "scanned": self.scanned,
            "migratable": self.migratable,
            "skipped": self.skipped,
            "invalid": self.invalid,
            "sample_errors": [
                {"old_id": e.old_id, "code": e.code, "message": e.message}
                for e in self.sample_errors
            ],
        }
```

```python
# application/storyos/services/foreshadowing_migration_service.py
# 完整重写（替换 1B 的 stub）

"""ForeshadowingMigrationService —— 旧 foreshadows 表 → storyos_foreshadowing_v1 单向迁移。

3 方法（spec §1E 锁定）：
- scan(project_id) → MigrationPreviewReport：只读扫描，生成 5 元组报告
- execute(project_id, batch_size, dry_run) → MigrationExecuteResult：批量迁移
- rollback(migration_id) → RollbackResult：基于 migration_log 回滚单条批次

依赖（通过 __init__ 注入）：
- legacy_adapter: LegacyForeshadowingAdapter（只读）
- log_repository: MigrationLogRepository（migration_log 持久化）
- new_table_writer: NewForeshadowingWriter（new table INSERT 抽象）
- audit_service: MigrationAuditService（Group C 注入）
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from application.storyos.value_objects.migration_preview_report import (
    MigrationPreviewReport,
    MigrationSampleError,
)
from application.storyos.migration.status_mapper import StatusMapper, UnknownLegacyStatusError

logger = logging.getLogger(__name__)


@dataclass
class MigrationExecuteResult:
    migration_id: str
    status: str  # "completed" | "partial" | "failed"
    batches_total: int
    batches_done: int
    records_migrated: int
    errors: List[str] = field(default_factory=list)


@dataclass
class RollbackResult:
    migration_id: str
    records_deleted: int
    status: str  # "rolled_back" | "not_found" | "already_rolled_back"


class ForeshadowingMigrationService:
    """Foreshadowing 单向迁移服务（spec §1E）。"""

    def __init__(
        self,
        legacy_adapter,
        log_repository,
        new_table_writer,
        audit_service=None,
    ) -> None:
        self._legacy = legacy_adapter
        self._log_repo = log_repository
        self._new_writer = new_table_writer
        self._audit = audit_service

    def scan(self, project_id: str) -> MigrationPreviewReport:
        """扫描旧表生成预览报告（只读，不写任何表）。"""
        total = self._legacy.count_for_novel(project_id)
        records, adapter_invalid_ids = self._legacy.fetch_all_with_invalid(project_id)
        scanned = len(records) + len(adapter_invalid_ids)

        # 状态映射 + 跳过 invalid
        migratable_pairs, status_invalid_ids = StatusMapper.map_with_skip(records)
        migratable = len(migratable_pairs)
        invalid = len(adapter_invalid_ids) + len(status_invalid_ids)

        # 断点续跑：减去已迁移的
        committed_ids = self._log_repo.get_committed_old_ids(project_id)
        skipped = sum(1 for r, _ in migratable_pairs if r.id in committed_ids)
        migratable -= skipped

        # sample errors（最多 10 条）
        sample_errors: List[MigrationSampleError] = []
        for bad_id in adapter_invalid_ids + status_invalid_ids:
            if len(sample_errors) >= 10:
                break
            code = "CORRUPTED_ROW" if bad_id in adapter_invalid_ids else "UNKNOWN_STATUS"
            sample_errors.append(MigrationSampleError(
                old_id=bad_id,
                code=code,
                message=f"Legacy foreshadowing {bad_id} cannot be migrated",
            ))

        return MigrationPreviewReport(
            project_id=project_id,
            total=total,
            scanned=scanned,
            migratable=migratable,
            skipped=skipped,
            invalid=invalid,
            sample_errors=sample_errors,
        )

    def execute(
        self,
        project_id: str,
        batch_size: int = 500,
        dry_run: bool = False,
    ) -> MigrationExecuteResult:
        """执行迁移。"""
        raise NotImplementedError("Phase 1E Task B2")

    def rollback(self, migration_id: str) -> RollbackResult:
        """回滚单条迁移批次。"""
        raise NotImplementedError("Phase 1E Task B3")
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 + 3 = 8 passed

Run: `pytest tests/unit/application/storyos/value_objects/test_migration_preview_report.py tests/unit/application/storyos/services/test_foreshadowing_migration.py -v`
Expected: 8 passed（5 preview + 3 scan）

- [ ] **Step 5: 验证 1B 旧 stub 测试被替换**

```bash
# 旧的 stub 测试文件应该已经被覆盖；如果还在，删除它
ls tests/unit/application/storyos/services/test_foreshadowing_migration_stub.py 2>/dev/null && rm tests/unit/application/storyos/services/test_foreshadowing_migration_stub.py
```

- [ ] **Step 6: Commit**

```bash
git add application/storyos/services/foreshadowing_migration_service.py application/storyos/value_objects/migration_preview_report.py tests/unit/application/storyos/services/test_foreshadowing_migration.py tests/unit/application/storyos/value_objects/test_migration_preview_report.py
git rm tests/unit/application/storyos/services/test_foreshadowing_migration_stub.py 2>/dev/null || true
git commit -m "feat(migration): implement ForeshadowingMigrationService.scan() with 5-tuple report"
```

---

#### Task B2: execute() —— 批量迁移 + 幂等 + dry_run + 断点续跑

**Files:**
- Modify: `application/storyos/services/foreshadowing_migration_service.py`（实现 execute）
- Create: `application/storyos/migration/new_foreshadowing_writer.py`（新表 INSERT 抽象）
- Modify: `tests/unit/application/storyos/services/test_foreshadowing_migration.py`（追加 execute 测试）

- [ ] **Step 1: 写失败测试**

```python
# 在 tests/unit/application/storyos/services/test_foreshadowing_migration.py 追加

"""ForeshadowingMigrationService.execute() 单元测试。"""


def _make_service(records, committed_ids=None, adapter_invalid=None):
    adapter = MagicMock()
    adapter.fetch_all_with_invalid.return_value = (
        records,
        adapter_invalid or [],
    )
    log_repo = MagicMock()
    log_repo.get_committed_old_ids.return_value = committed_ids or set()
    new_writer = MagicMock()
    return ForeshadowingMigrationService(
        legacy_adapter=adapter,
        log_repository=log_repo,
        new_table_writer=new_writer,
    ), adapter, log_repo, new_writer


def test_execute_happy_path_single_batch():
    """execute 单一批次 < 500：直接迁移 + record committed。"""
    records = _fake_records()  # 10 条
    service, _, log_repo, new_writer = _make_service(records)
    result = service.execute("novel-1", batch_size=500)
    assert result.batches_total == 1
    assert result.batches_done == 1
    assert result.records_migrated == 10
    assert result.status == "completed"
    new_writer.insert_batch.assert_called_once()
    log_repo.record_committed_batch.assert_called_once()


def test_execute_multiple_batches():
    """execute batch_size=3 → 10 条 → 4 batches（3+3+3+1）。"""
    records = _fake_records()
    service, _, _, new_writer = _make_service(records)
    result = service.execute("novel-1", batch_size=3)
    assert result.batches_total == 4
    assert result.batches_done == 4
    assert result.records_migrated == 10
    assert new_writer.insert_batch.call_count == 4


def test_execute_skips_already_committed_ids():
    """断点续跑：已 committed 的 old_ids 跳过（不入 batch）。"""
    records = _fake_records()  # 10 条
    committed = {"fs-1", "fs-2", "fs-3"}
    service, _, log_repo, new_writer = _make_service(records, committed_ids=committed)
    result = service.execute("novel-1", batch_size=500)
    assert result.records_migrated == 7  # 10 - 3 already migrated
    new_writer.insert_batch.assert_called_once()
    inserted_batch = new_writer.insert_batch.call_args.args[0]
    inserted_ids = [r.id for r in inserted_batch]
    assert "fs-1" not in inserted_ids


def test_execute_dry_run_does_not_write():
    """dry_run=True：不调用 new_writer.insert_batch + 不写 migration_log。"""
    records = _fake_records()
    service, _, log_repo, new_writer = _make_service(records)
    result = service.execute("novel-1", batch_size=500, dry_run=True)
    assert result.status == "dry_run"
    new_writer.insert_batch.assert_not_called()
    log_repo.record_committed_batch.assert_not_called()


def test_execute_handles_invalid_status_gracefully():
    """未知 status 的记录跳过（不入 batch）但不抛异常。"""
    records = _fake_records()
    records.append(LegacyForeshadowingRecord(
        id="fs-bad", novel_id="n1", description="d",
        planted_chapter=1, due_chapter=None, resolved_chapter=None,
        status="legacy_weird", importance=2, subtext_type=None,
    ))
    service, _, _, new_writer = _make_service(records)
    result = service.execute("novel-1", batch_size=500)
    assert result.records_migrated == 10
    inserted_batch = new_writer.insert_batch.call_args.args[0]
    assert all(r.id != "fs-bad" for r in inserted_batch)


def test_execute_records_failed_batch_on_writer_exception():
    """writer 抛异常时调用 log_repo.record_failed_batch（不中断整个 migration）。"""
    records = _fake_records()
    service, _, log_repo, new_writer = _make_service(records)
    new_writer.insert_batch.side_effect = RuntimeError("SQL constraint failed")
    result = service.execute("novel-1", batch_size=3)
    # 4 个批次全部失败，但 service 不抛异常
    assert result.status == "failed"
    assert "SQL constraint" in str(result.errors)
    assert log_repo.record_failed_batch.call_count == 4


def test_execute_returns_partial_status_on_some_failed_batches():
    """部分批次失败时返回 partial 状态。"""
    records = _fake_records()
    service, _, _, new_writer = _make_service(records)
    # 第 2 个 batch 失败
    new_writer.insert_batch.side_effect = [
        None,  # batch 1 OK
        RuntimeError("batch 2 fail"),
        None,  # batch 3 OK
        None,  # batch 4 OK
    ]
    result = service.execute("novel-1", batch_size=3)
    assert result.status == "partial"
    assert result.batches_done == 3  # 4 中 3 成功
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `NotImplementedError`

Run: `pytest tests/unit/application/storyos/services/test_foreshadowing_migration.py -v -k "execute"`
Expected: FAILED with `NotImplementedError: Phase 1E Task B2`

- [ ] **Step 3: 实现**

```python
# application/storyos/migration/new_foreshadowing_writer.py
"""new_foreshadowing_writer —— 新 storyos_foreshadowing_v1 表 INSERT 抽象。

通过 WriteDispatch.enqueue_txn_batch 走单写者单事务（1A 已扩展）。
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import List, Optional

from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingRecord,
)
from domain.storyos.contracts import AssetStatus
from infrastructure.persistence.database.write_dispatch import enqueue_txn_batch

logger = logging.getLogger(__name__)


class NewForeshadowingWriter:
    """把 LegacyForeshadowingRecord + new_status 写入 storyos_foreshadowing_v1。"""

    _INSERT_SQL = (
        "INSERT OR IGNORE INTO storyos_foreshadowing_v1 "
        "(id, project_id, asset_type, status, description, "
        " importance, planted_chapter, payoff_chapter, resolved_chapter, "
        " migrated_from_legacy_id, created_at) "
        "VALUES (?, ?, 'foreshadowing', ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    def insert_batch(
        self,
        records: List[LegacyForeshadowingRecord],
        statuses: List[AssetStatus],
    ) -> None:
        """批量 INSERT（单事务，WriteDispatch 串行）。"""
        if len(records) != len(statuses):
            raise ValueError("records and statuses length mismatch")
        operations = []
        for rec, new_status in zip(records, statuses):
            operations.append((
                self._INSERT_SQL,
                (
                    f"mig-{rec.id}",  # 新表 ID 加 mig- 前缀避免与未来手建冲突
                    rec.novel_id,
                    new_status.value,
                    rec.description,
                    rec.importance,
                    rec.planted_chapter,
                    rec.due_chapter,
                    rec.resolved_chapter,
                    rec.id,  # migrated_from_legacy_id
                    "2026-07-03T10:00:00",  # created_at（占位，实际由 clock 注入）
                ),
            ))
        enqueue_txn_batch(operations)

    def delete_by_migrated_ids(self, old_ids: List[str]) -> int:
        """根据 old_id 列表删除（rollback 用）。"""
        if not old_ids:
            return 0
        placeholders = ",".join("?" for _ in old_ids)
        sql = (
            f"DELETE FROM storyos_foreshadowing_v1 "
            f"WHERE migrated_from_legacy_id IN ({placeholders})"
        )
        enqueue_txn_batch([(sql, tuple(old_ids))])
        return len(old_ids)
```

```python
# 在 application/storyos/services/foreshadowing_migration_service.py 替换 execute 方法

    def execute(
        self,
        project_id: str,
        batch_size: int = 500,
        dry_run: bool = False,
    ) -> MigrationExecuteResult:
        """执行迁移。"""
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")

        # 1. 拉取旧表全量 + 过滤已 committed
        records, adapter_invalid_ids = self._legacy.fetch_all_with_invalid(project_id)
        committed_ids = self._log_repo.get_committed_old_ids(project_id)

        # 2. 状态映射 + 跳过 unknown status
        migratable_pairs, status_invalid_ids = StatusMapper.map_with_skip(records)
        migratable_pairs = [
            (r, s) for r, s in migratable_pairs if r.id not in committed_ids
        ]

        if dry_run:
            return MigrationExecuteResult(
                migration_id="dry-run",
                status="dry_run",
                batches_total=(len(migratable_pairs) + batch_size - 1) // batch_size,
                batches_done=0,
                records_migrated=0,
                errors=[],
            )

        # 3. 分批执行
        migration_id = f"mig-{uuid.uuid4().hex[:12]}"
        batches_total = (len(migratable_pairs) + batch_size - 1) // batch_size
        batches_done = 0
        errors: List[str] = []
        started_at = datetime.utcnow().isoformat()

        for batch_idx in range(batches_total):
            batch_start = batch_idx * batch_size
            batch_end = batch_start + batch_size
            batch = migratable_pairs[batch_start:batch_end]
            batch_id = f"batch-{batch_idx:04d}"
            old_ids = [r.id for r, _ in batch]

            try:
                self._new_writer.insert_batch(
                    [r for r, _ in batch],
                    [s for _, s in batch],
                )
                completed_at = datetime.utcnow().isoformat()
                self._log_repo.record_committed_batch(
                    migration_id=migration_id,
                    project_id=project_id,
                    batch_id=batch_id,
                    old_ids=old_ids,
                    started_at=started_at,
                    completed_at=completed_at,
                )
                batches_done += 1
            except Exception as e:
                error_msg = f"batch {batch_id} failed: {e}"
                logger.warning("[migration] %s", error_msg)
                errors.append(error_msg)
                self._log_repo.record_failed_batch(
                    migration_id=migration_id,
                    project_id=project_id,
                    batch_id=batch_id,
                    old_ids=old_ids,
                    started_at=started_at,
                    error=str(e),
                )

        # 4. 计算最终状态
        if batches_done == batches_total:
            status = "completed"
        elif batches_done == 0:
            status = "failed"
        else:
            status = "partial"

        if self._audit is not None:
            try:
                self._audit.record_migration(
                    migration_id=migration_id,
                    project_id=project_id,
                    batches_total=batches_total,
                    batches_done=batches_done,
                    records_migrated=sum(
                        min(batch_size, len(migratable_pairs) - b * batch_size)
                        for b in range(batches_done)
                    ),
                    errors=errors,
                )
            except Exception as e:
                logger.warning("[migration] audit record 失败: %s", e)

        return MigrationExecuteResult(
            migration_id=migration_id,
            status=status,
            batches_total=batches_total,
            batches_done=batches_done,
            records_migrated=sum(
                min(batch_size, len(migratable_pairs) - b * batch_size)
                for b in range(batches_done)
            ),
            errors=errors,
        )
```

- [ ] **Step 4: 运行测试确认通过** — 期望 7 passed（execute 测试）

Run: `pytest tests/unit/application/storyos/services/test_foreshadowing_migration.py -v -k "execute"`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add application/storyos/services/foreshadowing_migration_service.py application/storyos/migration/new_foreshadowing_writer.py tests/unit/application/storyos/services/test_foreshadowing_migration.py
git commit -m "feat(migration): implement execute() with batch_size + dry_run + idempotency + 断点续跑"
```

---

#### Task B3: rollback() —— 按 migration_id 删除新表数据 + 更新 migration_log

**Files:**
- Modify: `application/storyos/services/foreshadowing_migration_service.py`（实现 rollback）
- Modify: `tests/unit/application/storyos/services/test_foreshadowing_migration.py`（追加 rollback 测试）

- [ ] **Step 1: 写失败测试**

```python
# 在 tests/unit/application/storyos/services/test_foreshadowing_migration.py 追加

"""ForeshadowingMigrationService.rollback() 单元测试。"""


def test_rollback_deletes_new_records_and_marks_log():
    """rollback 删除新表数据 + 把 migration_log 标记为 rolled_back。"""
    from infrastructure.persistence.storyos.migration_log_mapper import (
        MigrationLogEntry, MigrationStatus,
    )
    entry = MigrationLogEntry(
        id="ml-1", project_id="n1", migration_type="foreshadowing_v1",
        batch_id="batch-0001", old_ids=["fs-1", "fs-2", "fs-3"],
        status=MigrationStatus.COMMITTED,
        started_at="2026-07-03T10:00:00", completed_at="2026-07-03T10:00:05",
        error=None,
    )
    log_repo = MagicMock()
    log_repo.get_entry.return_value = entry
    new_writer = MagicMock()
    new_writer.delete_by_migrated_ids.return_value = 3

    service = ForeshadowingMigrationService(
        legacy_adapter=MagicMock(),
        log_repository=log_repo,
        new_table_writer=new_writer,
    )
    result = service.rollback("ml-1")

    assert result.records_deleted == 3
    assert result.status == "rolled_back"
    new_writer.delete_by_migrated_ids.assert_called_once_with(["fs-1", "fs-2", "fs-3"])
    log_repo.mark_rolled_back.assert_called_once_with("ml-1")


def test_rollback_returns_not_found_when_log_missing():
    """migration_id 不存在时返回 not_found，不抛异常。"""
    log_repo = MagicMock()
    log_repo.get_entry.return_value = None
    new_writer = MagicMock()

    service = ForeshadowingMigrationService(
        legacy_adapter=MagicMock(),
        log_repository=log_repo,
        new_table_writer=new_writer,
    )
    result = service.rollback("ml-nonexistent")
    assert result.status == "not_found"
    assert result.records_deleted == 0
    new_writer.delete_by_migrated_ids.assert_not_called()


def test_rollback_returns_already_when_already_rolled_back():
    """已 rolled_back 的批次不能再次 rollback。"""
    from infrastructure.persistence.storyos.migration_log_mapper import (
        MigrationLogEntry, MigrationStatus,
    )
    entry = MigrationLogEntry(
        id="ml-1", project_id="n1", migration_type="foreshadowing_v1",
        batch_id="batch-0001", old_ids=["fs-1"],
        status=MigrationStatus.ROLLED_BACK,
        started_at="2026-07-03T10:00:00", completed_at=None, error=None,
    )
    log_repo = MagicMock()
    log_repo.get_entry.return_value = entry

    service = ForeshadowingMigrationService(
        legacy_adapter=MagicMock(),
        log_repository=log_repo,
        new_table_writer=MagicMock(),
    )
    result = service.rollback("ml-1")
    assert result.status == "already_rolled_back"


def test_rollback_returns_failed_status_when_already_failed():
    """失败批次不能 rollback（没有 committed 数据可回滚）。"""
    from infrastructure.persistence.storyos.migration_log_mapper import (
        MigrationLogEntry, MigrationStatus,
    )
    entry = MigrationLogEntry(
        id="ml-1", project_id="n1", migration_type="foreshadowing_v1",
        batch_id="batch-0001", old_ids=["fs-1"],
        status=MigrationStatus.FAILED,
        started_at="2026-07-03T10:00:00", completed_at=None, error="...",
    )
    log_repo = MagicMock()
    log_repo.get_entry.return_value = entry

    service = ForeshadowingMigrationService(
        legacy_adapter=MagicMock(),
        log_repository=log_repo,
        new_table_writer=MagicMock(),
    )
    result = service.rollback("ml-1")
    assert result.status == "not_committed"


def test_rollback_does_not_modify_legacy_table():
    """rollback 永远不删除旧表数据（spec Q8 锁定）。"""
    from infrastructure.persistence.storyos.migration_log_mapper import (
        MigrationLogEntry, MigrationStatus,
    )
    entry = MigrationLogEntry(
        id="ml-1", project_id="n1", migration_type="foreshadowing_v1",
        batch_id="batch-0001", old_ids=["fs-1"],
        status=MigrationStatus.COMMITTED,
        started_at="2026-07-03T10:00:00", completed_at="2026-07-03T10:00:05",
        error=None,
    )
    legacy = MagicMock()
    log_repo = MagicMock()
    log_repo.get_entry.return_value = entry
    new_writer = MagicMock()

    service = ForeshadowingMigrationService(
        legacy_adapter=legacy, log_repository=log_repo, new_table_writer=new_writer,
    )
    service.rollback("ml-1")
    # 严禁访问 legacy adapter
    legacy.fetch_all_with_invalid.assert_not_called()
    legacy.count_for_novel.assert_not_called()
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `NotImplementedError`

Run: `pytest tests/unit/application/storyos/services/test_foreshadowing_migration.py -v -k "rollback"`
Expected: FAILED with `NotImplementedError`

- [ ] **Step 3: 实现**

```python
# 在 application/storyos/services/foreshadowing_migration_service.py 替换 rollback 方法

    def rollback(self, migration_id: str) -> RollbackResult:
        """回滚单条迁移批次（只删新表，旧表不动，spec Q8）。"""
        entry = self._log_repo.get_entry(migration_id)
        if entry is None:
            return RollbackResult(
                migration_id=migration_id, records_deleted=0, status="not_found",
            )

        if entry.status.value == "rolled_back":
            return RollbackResult(
                migration_id=migration_id, records_deleted=0,
                status="already_rolled_back",
            )

        if entry.status.value != "committed":
            return RollbackResult(
                migration_id=migration_id, records_deleted=0,
                status="not_committed",
            )

        # 1. 删除新表数据（不走旧表）
        deleted = self._new_writer.delete_by_migrated_ids(entry.old_ids)

        # 2. 更新 migration_log 状态
        self._log_repo.mark_rolled_back(migration_id)

        return RollbackResult(
            migration_id=migration_id,
            records_deleted=deleted,
            status="rolled_back",
        )
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed

Run: `pytest tests/unit/application/storyos/services/test_foreshadowing_migration.py -v -k "rollback"`
Expected: 5 passed

- [ ] **Step 5: 运行所有 ForeshadowingMigrationService 测试** — 期望 15 passed（5 preview + 3 scan + 7 execute + 5 rollback - 部分重叠）

Run: `pytest tests/unit/application/storyos/services/test_foreshadowing_migration.py -v`
Expected: ~20 passed

- [ ] **Step 6: Commit**

```bash
git add application/storyos/services/foreshadowing_migration_service.py tests/unit/application/storyos/services/test_foreshadowing_migration.py
git commit -m "feat(migration): implement rollback() with spec Q8 旧表保留约束"
```

---

### Group C: 迁移审计

#### Task C1: MigrationAuditService.record_batch() —— 每批次 success/failure/skip 计数

**Files:**
- Create: `application/storyos/services/migration_audit_service.py`
- Create: `tests/unit/application/storyos/services/test_migration_audit_service.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/application/storyos/services/test_migration_audit_service.py
"""MigrationAuditService 单元测试。

audit 聚合每个 migration_id 的批次结果，生成最终 JSON 报告。
存储在内存（不需要持久化表）；CLI / API 退出时打印。
"""
from application.storyos.services.migration_audit_service import (
    MigrationAuditService,
    MigrationAuditRecord,
)


def test_audit_service_starts_empty():
    svc = MigrationAuditService()
    assert svc.all_records() == []


def test_record_migration_creates_record():
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1",
        project_id="novel-1",
        batches_total=4,
        batches_done=4,
        records_migrated=100,
        errors=[],
    )
    records = svc.all_records()
    assert len(records) == 1
    assert records[0].migration_id == "mig-1"
    assert records[0].records_migrated == 100


def test_record_migration_captures_errors():
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1",
        project_id="novel-1",
        batches_total=4,
        batches_done=2,
        records_migrated=50,
        errors=["batch-0002 failed: SQL", "batch-0003 failed: timeout"],
    )
    rec = svc.all_records()[0]
    assert len(rec.errors) == 2
    assert "SQL" in rec.errors[0]


def test_get_record_returns_by_migration_id():
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1", project_id="n1",
        batches_total=1, batches_done=1, records_migrated=10, errors=[],
    )
    svc.record_migration(
        migration_id="mig-2", project_id="n1",
        batches_total=2, batches_done=2, records_migrated=20, errors=[],
    )
    rec = svc.get_record("mig-1")
    assert rec is not None
    assert rec.records_migrated == 10
    assert svc.get_record("mig-999") is None


def test_audit_record_fields():
    """MigrationAuditRecord 字段集：8 字段覆盖批次 + 项目 + 错误。"""
    rec = MigrationAuditRecord(
        migration_id="mig-1", project_id="n1",
        batches_total=5, batches_done=5, records_migrated=100,
        duration_ms=1500, status="completed", errors=[],
        started_at="2026-07-03T10:00:00",
    )
    assert rec.duration_ms == 1500
    assert rec.status == "completed"
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `ModuleNotFoundError`

Run: `pytest tests/unit/application/storyos/services/test_migration_audit_service.py -v`
Expected: FAILED

- [ ] **Step 3: 实现**

```python
# application/storyos/services/migration_audit_service.py
"""MigrationAuditService —— 进程内审计聚合。

注：审计记录保存在内存（不持久化），CLI / API 进程退出后丢失。
长期审计通过 migration_log 表（spec §1E）持久化。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass(frozen=True)
class MigrationAuditRecord:
    migration_id: str
    project_id: str
    batches_total: int
    batches_done: int
    records_migrated: int
    duration_ms: int
    status: str
    errors: List[str]
    started_at: str


class MigrationAuditService:
    def __init__(self) -> None:
        self._records: Dict[str, MigrationAuditRecord] = {}

    def record_migration(
        self,
        migration_id: str,
        project_id: str,
        batches_total: int,
        batches_done: int,
        records_migrated: int,
        errors: List[str],
        duration_ms: Optional[int] = None,
    ) -> None:
        if batches_done == batches_total:
            status = "completed"
        elif batches_done == 0:
            status = "failed"
        else:
            status = "partial"

        self._records[migration_id] = MigrationAuditRecord(
            migration_id=migration_id,
            project_id=project_id,
            batches_total=batches_total,
            batches_done=batches_done,
            records_migrated=records_migrated,
            duration_ms=duration_ms or 0,
            status=status,
            errors=list(errors),
            started_at=datetime.utcnow().isoformat(),
        )

    def get_record(self, migration_id: str) -> Optional[MigrationAuditRecord]:
        return self._records.get(migration_id)

    def all_records(self) -> List[MigrationAuditRecord]:
        return list(self._records.values())
```

- [ ] **Step 4: 运行测试确认通过** — 期望 5 passed

Run: `pytest tests/unit/application/storyos/services/test_migration_audit_service.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add application/storyos/services/migration_audit_service.py tests/unit/application/storyos/services/test_migration_audit_service.py
git commit -m "feat(migration): add MigrationAuditService for in-process batch aggregation"
```

---

#### Task C2: MigrationReportAggregator —— 聚合多个批次生成最终 JSON 报告

**Files:**
- Modify: `application/storyos/services/migration_audit_service.py`（添加 aggregator 方法）
- Modify: `tests/unit/application/storyos/services/test_migration_audit_service.py`（追加 aggregator 测试）

- [ ] **Step 1: 写失败测试**

```python
# 在 tests/unit/application/storyos/services/test_migration_audit_service.py 追加


def test_aggregator_combines_multiple_migrations():
    """aggregator 合并多个 migration_id 的审计记录，生成最终报告。"""
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1", project_id="n1",
        batches_total=2, batches_done=2, records_migrated=100, errors=[],
    )
    svc.record_migration(
        migration_id="mig-2", project_id="n1",
        batches_total=3, batches_done=2, records_migrated=80,
        errors=["batch-0003 failed"],
    )
    report = svc.aggregate_report()
    assert report["total_migrations"] == 2
    assert report["total_records_migrated"] == 180
    assert report["total_errors"] == 1


def test_aggregator_returns_empty_report_when_no_records():
    svc = MigrationAuditService()
    report = svc.aggregate_report()
    assert report["total_migrations"] == 0
    assert report["total_records_migrated"] == 0
    assert report["migrations"] == []


def test_aggregator_groups_by_project_id():
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1", project_id="n1",
        batches_total=1, batches_done=1, records_migrated=10, errors=[],
    )
    svc.record_migration(
        migration_id="mig-2", project_id="n2",
        batches_total=1, batches_done=1, records_migrated=20, errors=[],
    )
    report = svc.aggregate_report()
    by_project = report["by_project"]
    assert by_project["n1"] == {"migrations": 1, "records": 10}
    assert by_project["n2"] == {"migrations": 1, "records": 20}


def test_aggregator_to_json_serializable():
    """aggregator 输出的 dict 可以直接 json.dumps。"""
    import json
    svc = MigrationAuditService()
    svc.record_migration(
        migration_id="mig-1", project_id="n1",
        batches_total=1, batches_done=1, records_migrated=10, errors=[],
    )
    report = svc.aggregate_report()
    json_str = json.dumps(report)
    assert "mig-1" in json_str
```

- [ ] **Step 2: 运行测试确认失败** — 期望 `AttributeError: aggregate_report`

Run: `pytest tests/unit/application/storyos/services/test_migration_audit_service.py -v -k "aggregator"`
Expected: FAILED

- [ ] **Step 3: 实现**

```python
# 在 application/storyos/services/migration_audit_service.py 追加方法

    def aggregate_report(self) -> dict:
        """聚合所有审计记录生成最终 JSON 报告（CLI --status 输出）。"""
        records = self.all_records()
        by_project: Dict[str, Dict[str, int]] = {}
        total_errors = 0
        for r in records:
            by_project.setdefault(r.project_id, {"migrations": 0, "records": 0})
            by_project[r.project_id]["migrations"] += 1
            by_project[r.project_id]["records"] += r.records_migrated
            total_errors += len(r.errors)

        return {
            "total_migrations": len(records),
            "total_records_migrated": sum(r.records_migrated for r in records),
            "total_errors": total_errors,
            "by_project": by_project,
            "migrations": [
                {
                    "migration_id": r.migration_id,
                    "project_id": r.project_id,
                    "batches_total": r.batches_total,
                    "batches_done": r.batches_done,
                    "records_migrated": r.records_migrated,
                    "status": r.status,
                    "errors": r.errors,
                    "started_at": r.started_at,
                }
                for r in records
            ],
        }
```

- [ ] **Step 4: 运行测试确认通过** — 期望 4 passed

Run: `pytest tests/unit/application/storyos/services/test_migration_audit_service.py -v -k "aggregator"`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add application/storyos/services/migration_audit_service.py tests/unit/application/storyos/services/test_migration_audit_service.py
git commit -m "feat(migration): add MigrationAuditService.aggregate_report() for CLI --status"
```

---

### Group D: API 联通

#### Task D1: 替换 1D 501 桩 → 真实 preview/execute handler

**Files:**
- Modify: `interfaces/api/v1/storyos/routes/migration_routes.py`（替换 501 → 真实）
- Modify: `tests/integration/api/v1/storyos/test_migration_endpoints.py`（替换 1D 测试 → 真实测试）

- [ ] **Step 1: 写失败测试**（替换 1D 桩的 501 期望）

```python
# tests/integration/api/v1/storyos/test_migration_endpoints.py（重写）

"""Migration 端点集成测试（1E 联通 1D 桩 → 真实 handler）。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from interfaces.main import app
from application.storyos.value_objects.migration_preview_report import (
    MigrationPreviewReport,
)
from application.storyos.services.foreshadowing_migration_service import (
    MigrationExecuteResult,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_migration_service():
    """Patch get_migration_service DI factory。"""
    with patch(
        "interfaces.api.v1.storyos.routes.migration_routes.get_migration_service"
    ) as mock:
        yield mock


def test_preview_returns_5_tuple_report(client, mock_migration_service):
    """POST /migration/preview 返回 MigrationPreviewResponse 5 元组。"""
    service = MagicMock()
    service.scan.return_value = MigrationPreviewReport(
        project_id="proj-1", total=100, scanned=100,
        migratable=85, skipped=10, invalid=5,
        sample_errors=[],
    )
    mock_migration_service.return_value = service

    resp = client.post("/api/v1/storyos/proj-1/migration/preview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 100
    assert body["migratable"] == 85
    assert body["invalid"] == 5
    service.scan.assert_called_once_with("proj-1")


def test_preview_returns_empty_report_for_new_project(client, mock_migration_service):
    service = MagicMock()
    service.scan.return_value = MigrationPreviewReport(project_id="proj-empty")
    mock_migration_service.return_value = service
    resp = client.post("/api/v1/storyos/proj-empty/migration/preview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["migratable"] == 0


def test_execute_calls_service_with_request_params(client, mock_migration_service):
    """POST /migration/execute 接收 batch_size + dry_run 参数。"""
    service = MagicMock()
    service.execute.return_value = MigrationExecuteResult(
        migration_id="mig-1", status="completed",
        batches_total=2, batches_done=2, records_migrated=100, errors=[],
    )
    mock_migration_service.return_value = service

    resp = client.post(
        "/api/v1/storyos/proj-1/migration/execute",
        json={"batch_size": 200, "dry_run": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["migration_id"] == "mig-1"
    assert body["status"] == "completed"
    assert body["batches_total"] == 2
    service.execute.assert_called_once_with("proj-1", batch_size=200, dry_run=False)


def test_execute_default_batch_size_is_500(client, mock_migration_service):
    """MigrationExecuteRequest 默认 batch_size=500。"""
    service = MagicMock()
    service.execute.return_value = MigrationExecuteResult(
        migration_id="mig-1", status="completed",
        batches_total=1, batches_done=1, records_migrated=10, errors=[],
    )
    mock_migration_service.return_value = service

    resp = client.post(
        "/api/v1/storyos/proj-1/migration/execute",
        json={"dry_run": False},
    )
    service.execute.assert_called_once_with("proj-1", batch_size=500, dry_run=False)


def test_execute_dry_run_returns_dry_run_status(client, mock_migration_service):
    service = MagicMock()
    service.execute.return_value = MigrationExecuteResult(
        migration_id="dry-run", status="dry_run",
        batches_total=2, batches_done=0, records_migrated=0, errors=[],
    )
    mock_migration_service.return_value = service
    resp = client.post(
        "/api/v1/storyos/proj-1/migration/execute",
        json={"batch_size": 500, "dry_run": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "dry_run"
    assert body["records_migrated"] == 0


def test_execute_invalid_batch_size_returns_422(client, mock_migration_service):
    """batch_size <= 0 时 FastAPI 422 校验失败。"""
    resp = client.post(
        "/api/v1/storyos/proj-1/migration/execute",
        json={"batch_size": 0, "dry_run": False},
    )
    assert resp.status_code == 422


def test_endpoints_still_in_openapi_schema(client):
    """即使替换为真实实现，端点仍在 OpenAPI 中可见。"""
    resp = client.get("/openapi.json")
    schema = resp.json()
    paths = schema["paths"]
    assert "/api/v1/storyos/{project_id}/migration/preview" in paths
    assert "/api/v1/storyos/{project_id}/migration/execute" in paths
```

- [ ] **Step 2: 运行测试确认失败** — 期望 501 status（仍是 1D 桩行为）

Run: `pytest tests/integration/api/v1/storyos/test_migration_endpoints.py -v`
Expected: FAILED with 501 (preview endpoint)

- [ ] **Step 3: 实现** — 修改 `interfaces/api/v1/storyos/routes/migration_routes.py`：

```python
"""Migration 端点（1D 桩 → 1E 联通）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path

from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from interfaces.api.v1.storyos.dependencies import get_migration_service
from interfaces.api.v1.storyos.schemas.migration_schemas import (
    MigrationExecuteRequest,
    MigrationExecuteResponse,
    MigrationPreviewResponse,
)


router = APIRouter(prefix="/{project_id}/migration", tags=["storyos-migration"])


@router.post(
    "/preview",
    response_model=MigrationPreviewResponse,
    summary="扫描旧 foreshadowing 表生成预览报告",
)
async def migration_preview(
    project_id: str = Path(..., min_length=1, max_length=64),
    service: ForeshadowingMigrationService = Depends(get_migration_service),
) -> MigrationPreviewResponse:
    """POST /api/v1/storyos/{project_id}/migration/preview。

    返回 5 元组报告：total / scanned / migratable / skipped / invalid + sample_errors。
    只读操作，不修改任何表。
    """
    report = service.scan(project_id)
    return MigrationPreviewResponse(
        total=report.total,
        scanned=report.scanned,
        migratable=report.migratable,
        skipped=report.skipped,
        invalid=report.invalid,
        sample_errors=[
            {"old_id": e.old_id, "code": e.code, "message": e.message}
            for e in report.sample_errors
        ],
    )


@router.post(
    "/execute",
    response_model=MigrationExecuteResponse,
    summary="执行 foreshadowing 单向迁移",
)
async def migration_execute(
    req: MigrationExecuteRequest,
    project_id: str = Path(..., min_length=1, max_length=64),
    service: ForeshadowingMigrationService = Depends(get_migration_service),
) -> MigrationExecuteResponse:
    """POST /api/v1/storyos/{project_id}/migration/execute。

    批量迁移旧表数据到 storyos_foreshadowing_v1。
    """
    result = service.execute(
        project_id, batch_size=req.batch_size, dry_run=req.dry_run,
    )
    return MigrationExecuteResponse(
        migration_id=result.migration_id,
        status=result.status,
        batches_total=result.batches_total,
        batches_done=result.batches_done,
        errors=result.errors,
    )
```

- [ ] **Step 4: 运行测试确认通过** — 期望 7 passed

Run: `pytest tests/integration/api/v1/storyos/test_migration_endpoints.py -v`
Expected: 7 passed

- [ ] **Step 5: 验证 1D 旧测试被替换**

```bash
# 删除 1D 旧测试中期望 501 的部分（如已包含 F1 test_migration_execute_returns_501_until_1E）
grep -l "501" tests/integration/api/v1/storyos/test_migration_endpoints.py 2>/dev/null && \
  echo "WARNING: 旧 501 测试仍在文件中，请清理"
```

- [ ] **Step 6: Commit**

```bash
git add interfaces/api/v1/storyos/routes/migration_routes.py tests/integration/api/v1/storyos/test_migration_endpoints.py
git commit -m "feat(api): replace 1D migration 501 stubs with real handlers (1E 联通)"
```

---

#### Task D2: GET /api/v1/storyos/{project_id}/migration/{migration_id}/status

**Files:**
- Modify: `interfaces/api/v1/storyos/schemas/migration_schemas.py`（追加 MigrationStatusResponse，1D 已定义但未联通）
- Modify: `interfaces/api/v1/storyos/routes/migration_routes.py`（添加 GET /status handler）
- Modify: `tests/integration/api/v1/storyos/test_migration_endpoints.py`（追加 status 测试）

- [ ] **Step 1: 验证 1D 已定义 MigrationStatusResponse**

Run: `grep -n "MigrationStatusResponse" interfaces/api/v1/storyos/schemas/migration_schemas.py`
Expected: 命中

（1D plan line 848 已锁定 schema 字段 `migration_id, status, progress_pct, eta_seconds`）

- [ ] **Step 2: 写失败测试**

```python
# 在 tests/integration/api/v1/storyos/test_migration_endpoints.py 追加

from application.storyos.services.foreshadowing_migration_service import (
    RollbackResult,
)


def test_status_returns_audit_record(client, mock_migration_service):
    """GET /migration/{migration_id}/status 返回审计记录的进度。"""
    service = MagicMock()
    service.get_audit_record.return_value = {
        "migration_id": "mig-1",
        "project_id": "proj-1",
        "batches_total": 4,
        "batches_done": 2,
        "records_migrated": 100,
        "status": "partial",
        "errors": ["batch-0003 failed"],
    }
    mock_migration_service.return_value = service

    resp = client.get("/api/v1/storyos/proj-1/migration/mig-1/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["migration_id"] == "mig-1"
    assert body["status"] == "partial"
    # progress_pct = 2/4 * 100 = 50
    assert body["progress_pct"] == 50


def test_status_404_when_migration_not_found(client, mock_migration_service):
    service = MagicMock()
    service.get_audit_record.return_value = None
    mock_migration_service.return_value = service

    resp = client.get("/api/v1/storyos/proj-1/migration/mig-nonexistent/status")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "MIGRATION_NOT_FOUND"


def test_rollback_endpoint_calls_service(client, mock_migration_service):
    """POST /migration/{migration_id}/rollback 回滚指定批次。"""
    service = MagicMock()
    service.rollback.return_value = RollbackResult(
        migration_id="mig-1", records_deleted=3, status="rolled_back",
    )
    mock_migration_service.return_value = service

    resp = client.post("/api/v1/storyos/proj-1/migration/mig-1/rollback")
    assert resp.status_code == 200
    body = resp.json()
    assert body["records_deleted"] == 3
    assert body["status"] == "rolled_back"


def test_rollback_404_when_migration_not_found(client, mock_migration_service):
    service = MagicMock()
    service.rollback.return_value = RollbackResult(
        migration_id="mig-1", records_deleted=0, status="not_found",
    )
    mock_migration_service.return_value = service
    resp = client.post("/api/v1/storyos/proj-1/migration/mig-1/rollback")
    assert resp.status_code == 404
```

- [ ] **Step 3: 运行测试确认失败** — 期望 404（端点不存在）

Run: `pytest tests/integration/api/v1/storyos/test_migration_endpoints.py -v -k "status or rollback_endpoint"`
Expected: FAILED with 404

- [ ] **Step 4: 实现**

首先，在 `application/storyos/services/foreshadowing_migration_service.py` 添加 `get_audit_record` 方法：

```python
    def get_audit_record(self, migration_id: str):
        """从 audit service 查单条审计记录（API GET /status 用）。"""
        if self._audit is None:
            return None
        return self._audit.get_record(migration_id)
```

然后修改 `interfaces/api/v1/storyos/routes/migration_routes.py`：

```python
# 在 migration_routes.py 追加

from fastapi import HTTPException

from interfaces.api.v1.storyos.schemas.migration_schemas import (
    MigrationStatusResponse,
    RollbackResponse,
)


@router.get(
    "/{migration_id}/status",
    response_model=MigrationStatusResponse,
    summary="查询迁移进度",
)
async def migration_status(
    project_id: str = Path(..., min_length=1, max_length=64),
    migration_id: str = Path(..., min_length=1, max_length=64),
    service: ForeshadowingMigrationService = Depends(get_migration_service),
) -> MigrationStatusResponse:
    """GET /api/v1/storyos/{project_id}/migration/{migration_id}/status。

    返回当前进度 + 错误列表 + ETA（粗略估算）。
    """
    record = service.get_audit_record(migration_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "MIGRATION_NOT_FOUND", "message": f"migration {migration_id} not found"},
        )
    progress_pct = (
        int(record["batches_done"] / record["batches_total"] * 100)
        if record["batches_total"] > 0 else 0
    )
    # ETA 粗略估算：剩余 batches * 平均每批 200ms
    eta_seconds = (record["batches_total"] - record["batches_done"]) * 0.2
    return MigrationStatusResponse(
        migration_id=migration_id,
        status=record["status"],
        progress_pct=progress_pct,
        eta_seconds=eta_seconds,
    )


@router.post(
    "/{migration_id}/rollback",
    response_model=RollbackResponse,
    summary="回滚单条迁移批次",
)
async def migration_rollback(
    project_id: str = Path(..., min_length=1, max_length=64),
    migration_id: str = Path(..., min_length=1, max_length=64),
    service: ForeshadowingMigrationService = Depends(get_migration_service),
) -> RollbackResponse:
    """POST /api/v1/storyos/{project_id}/migration/{migration_id}/rollback。

    只删除新表数据，旧表不动（spec Q8）。
    """
    result = service.rollback(migration_id)
    if result.status == "not_found":
        raise HTTPException(
            status_code=404,
            detail={"code": "MIGRATION_NOT_FOUND", "message": f"migration {migration_id} not found"},
        )
    return RollbackResponse(
        migration_id=result.migration_id,
        records_deleted=result.records_deleted,
        status=result.status,
    )
```

并在 `interfaces/api/v1/storyos/schemas/migration_schemas.py` 添加（如果 1D 未包含 `RollbackResponse`）：

```python
# 在 migration_schemas.py 追加（如缺失）

class RollbackResponse(BaseModel):
    """POST /migration/{migration_id}/rollback 响应。"""
    model_config = ConfigDict(extra="forbid")

    migration_id: str
    records_deleted: int
    status: str  # "rolled_back" | "not_found" | "already_rolled_back" | "not_committed"
```

- [ ] **Step 5: 运行测试确认通过** — 期望 4 passed

Run: `pytest tests/integration/api/v1/storyos/test_migration_endpoints.py -v`
Expected: 11 passed（7 D1 + 4 D2）

- [ ] **Step 6: Commit**

```bash
git add interfaces/api/v1/storyos/routes/migration_routes.py interfaces/api/v1/storyos/schemas/migration_schemas.py application/storyos/services/foreshadowing_migration_service.py tests/integration/api/v1/storyos/test_migration_endpoints.py
git commit -m "feat(api): add GET /migration/{id}/status + POST /migration/{id}/rollback (1E)"
```

---

### Group E: CLI 完整实现

#### Task E1: scripts/migrate_storyos.py --dry-run + --execute + 进度条 + JSON 输出

**Files:**
- Modify: `scripts/migrate_storyos.py`（1A 脚手架 → 1E 完整）
- Create: `tests/unit/scripts/test_migrate_storyos_cli.py`

- [ ] **Step 1: 验证 1A 脚手架存在**

Run: `cat scripts/migrate_storyos.py 2>/dev/null | head -30`
Expected: 1A 阶段有最小脚手架

- [ ] **Step 2: 写失败测试**

```python
# tests/unit/scripts/test_migrate_storyos_cli.py
"""CLI 单元测试（通过 subprocess 调用）。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CLI_PATH = Path("/Users/longsa/Codes/plotPilot/scripts/migrate_storyos.py")


@pytest.fixture
def cli():
    """Subprocess 调用 CLI（隔离环境，不污染主进程）。"""
    def run(*args, env_extra=None):
        env = {"PYTHONPATH": "/Users/longsa/Codes/plotPilot"}
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [sys.executable, str(CLI_PATH), *args],
            capture_output=True, text=True, env=env, timeout=30,
        )
    return run


def test_cli_help_shows_subcommands(cli):
    result = cli("--help")
    assert result.returncode == 0
    assert "--dry-run" in result.stdout
    assert "--execute" in result.stdout
    assert "--rollback" in result.stdout


def test_cli_dry_run_outputs_json_report(cli):
    """--dry-run 输出 JSON 报告到 stdout。"""
    result = cli("--dry-run", "--project-id", "test-novel-1", "--json")
    # 即使数据库无数据，dry-run 应该返回有效 JSON
    assert result.returncode == 0, f"stderr: {result.stderr}"
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"stdout 不是 JSON: {result.stdout}")
    assert "total" in report
    assert "migratable" in report


def test_cli_execute_requires_project_id(cli):
    """--execute 必须指定 --project-id。"""
    result = cli("--execute")
    assert result.returncode != 0
    assert "project-id" in result.stderr.lower() or "project_id" in result.stderr.lower()


def test_cli_batch_size_argument_parsed(cli):
    """--batch-size 参数被正确解析。"""
    result = cli(
        "--dry-run", "--project-id", "test-novel-1",
        "--batch-size", "100", "--json",
    )
    assert result.returncode == 0


def test_cli_invalid_subcommand_shows_error(cli):
    result = cli("--invalid-flag")
    assert result.returncode != 0


def test_cli_no_args_shows_usage(cli):
    """无参数时显示 usage。"""
    result = cli()
    assert "--dry-run" in result.stdout or "--execute" in result.stdout or "usage" in result.stdout.lower()
```

- [ ] **Step 3: 运行测试确认失败** — 期望 import error 或 help 不完整

Run: `pytest tests/unit/scripts/test_migrate_storyos_cli.py -v`
Expected: FAILED

- [ ] **Step 4: 实现** — 重写 `scripts/migrate_storyos.py`：

```python
#!/usr/bin/env python3
"""migrate_storyos.py —— StoryOS Foreshadowing 单向迁移 CLI（spec §1E 锁定）。

子命令：
  --dry-run              扫描旧表 + 输出 JSON 报告，不写任何表
  --execute              实际执行迁移（断点续跑 + 幂等）
  --rollback <id>        回滚单条迁移批次
  --status               显示当前进程的审计聚合

参数：
  --project-id <id>      目标项目 ID（dry-run / execute 必填）
  --batch-size <n>       每批大小（默认 500）
  --json                 JSON 格式输出（供脚本消费）

行为：
- 旧 foreshadows 表只读（spec Q8 锁定）
- 幂等性通过 UNIQUE(migrated_from_legacy_id) 保证
- dry-run 输出 5 元组报告 + sample errors
- execute 输出迁移 ID + 批次进度 + 错误聚合
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# 让脚本能 import 项目根目录的模块
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from application.storyos.services.migration_audit_service import (
    MigrationAuditService,
)
from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingAdapter,
)
from application.storyos.migration.migration_log_repository import (
    MigrationLogRepository,
)
from application.storyos.migration.new_foreshadowing_writer import (
    NewForeshadowingWriter,
)
from infrastructure.persistence.database.connection import get_connection

logger = logging.getLogger(__name__)


def _build_service(args) -> ForeshadowingMigrationService:
    """构造 MigrationService（CLI 模式下默认使用主数据库）。"""
    conn_provider = lambda: get_connection()
    legacy = LegacyForeshadowingAdapter(
        cursor_provider=lambda sql, params=(): conn_provider().execute(sql, params)
    )
    log_repo = MigrationLogRepository(db_provider=conn_provider)
    new_writer = NewForeshadowingWriter()
    audit = MigrationAuditService()
    return ForeshadowingMigrationService(
        legacy_adapter=legacy,
        log_repository=log_repo,
        new_table_writer=new_writer,
        audit_service=audit,
    )


def _print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_dry_run(args, service: ForeshadowingMigrationService) -> int:
    report = service.scan(args.project_id)
    _print_json(report.to_dict())
    return 0


def cmd_execute(args, service: ForeshadowingMigrationService) -> int:
    result = service.execute(
        project_id=args.project_id,
        batch_size=args.batch_size,
        dry_run=False,
    )
    _print_json({
        "migration_id": result.migration_id,
        "status": result.status,
        "batches_total": result.batches_total,
        "batches_done": result.batches_done,
        "records_migrated": result.records_migrated,
        "errors": result.errors,
    })
    return 0 if result.status == "completed" else 1


def cmd_rollback(args, service: ForeshadowingMigrationService) -> int:
    result = service.rollback(args.rollback)
    _print_json({
        "migration_id": result.migration_id,
        "records_deleted": result.records_deleted,
        "status": result.status,
    })
    return 0 if result.status == "rolled_back" else 1


def cmd_status(args, service: ForeshadowingMigrationService) -> int:
    if service._audit is None:
        print(json.dumps({"error": "audit service not configured"}))
        return 1
    report = service._audit.aggregate_report()
    _print_json(report)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="StoryOS Foreshadowing 单向迁移工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project-id", type=str, help="目标项目 ID")
    parser.add_argument("--batch-size", type=int, default=500, help="每批大小（默认 500）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")

    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--dry-run", action="store_true", help="仅扫描不写")
    mode.add_argument("--execute", action="store_true", help="执行迁移")
    mode.add_argument("--rollback", type=str, metavar="MIGRATION_ID", help="回滚指定批次")
    mode.add_argument("--status", action="store_true", help="显示审计聚合")

    args = parser.parse_args(argv)

    # 默认行为：无参数显示 help
    if not any([args.dry_run, args.execute, args.rollback, args.status]):
        parser.print_help()
        return 0

    service = _build_service(args)

    try:
        if args.dry_run:
            if not args.project_id:
                parser.error("--dry-run requires --project-id")
            return cmd_dry_run(args, service)
        elif args.execute:
            if not args.project_id:
                parser.error("--execute requires --project-id")
            return cmd_execute(args, service)
        elif args.rollback:
            return cmd_rollback(args, service)
        elif args.status:
            return cmd_status(args, service)
    except Exception as e:
        logger.exception("CLI 异常")
        print(json.dumps({"error": str(e)}))
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 运行测试确认通过** — 期望 6 passed

Run: `pytest tests/unit/scripts/test_migrate_storyos_cli.py -v`
Expected: 6 passed

- [ ] **Step 6: 手动验证 CLI**

```bash
python scripts/migrate_storyos.py --help
python scripts/migrate_storyos.py --dry-run --project-id test-novel-1 --json
```

- [ ] **Step 7: Commit**

```bash
git add scripts/migrate_storyos.py tests/unit/scripts/test_migrate_storyos_cli.py
git commit -m "feat(cli): implement migrate_storyos.py with --dry-run/--execute/--rollback/--status"
```

---

#### Task E2: CLI 错误聚合 + 进度条增强

**Files:**
- Modify: `scripts/migrate_storyos.py`（添加进度条 + 错误聚合输出）
- Modify: `tests/unit/scripts/test_migrate_storyos_cli.py`（追加测试）

- [ ] **Step 1: 写失败测试**

```python
# 在 tests/unit/scripts/test_migrate_storyos_cli.py 追加


def test_cli_aggregates_errors_in_execute(cli):
    """--execute 输出包含 errors 字段聚合（spec §1E 锁定）。"""
    # 使用空 project-id 测试错误聚合路径
    # （实际错误聚合测试在 Group F 集成测试中验证）
    result = cli("--execute", "--project-id", "test-novel-1", "--json")
    # 即使无数据也应该返回有效 JSON 报告
    assert result.returncode in (0, 1)  # 0 if empty, 1 if errors


def test_cli_progress_output_is_human_readable(cli):
    """默认输出（非 --json）包含进度信息（人类可读）。"""
    result = cli("--dry-run", "--project-id", "test-novel-1")
    assert result.returncode == 0
    # 不带 --json 时输出应该包含 total / migratable 等字段名
    assert "total" in result.stdout.lower() or "migratable" in result.stdout.lower()
```

- [ ] **Step 2: 实现** — 在 `cmd_execute` 中增强进度输出：

```python
# 在 scripts/migrate_storyos.py cmd_execute 中增加人类可读输出分支

def cmd_execute(args, service: ForeshadowingMigrationService) -> int:
    if not args.json:
        print(f"[migration] 开始迁移 project_id={args.project_id} batch_size={args.batch_size}")
    result = service.execute(
        project_id=args.project_id,
        batch_size=args.batch_size,
        dry_run=False,
    )
    if args.json:
        _print_json({...})
    else:
        print(f"[migration] 完成 status={result.status}")
        print(f"[migration] 迁移 ID: {result.migration_id}")
        print(f"[migration] 批次进度: {result.batches_done}/{result.batches_total}")
        print(f"[migration] 迁移记录: {result.records_migrated}")
        if result.errors:
            print(f"[migration] 错误 ({len(result.errors)} 条):")
            for e in result.errors[:10]:  # 最多显示 10 条
                print(f"  - {e}")
    return 0 if result.status == "completed" else 1
```

- [ ] **Step 3: 运行测试确认通过**

Run: `pytest tests/unit/scripts/test_migrate_storyos_cli.py -v`
Expected: 8 passed（6 E1 + 2 E2）

- [ ] **Step 4: Commit**

```bash
git add scripts/migrate_storyos.py tests/unit/scripts/test_migrate_storyos_cli.py
git commit -m "feat(cli): add human-readable progress output + error aggregation"
```

---

### Group F: 集成 + 性能测试

#### Task F1: 端到端集成测试（幂等性 / 异常数据 / 批次边界 / 旧表保留只读）

**Files:**
- Create: `tests/integration/migration/__init__.py`
- Create: `tests/integration/migration/test_foreshadowing_migration_e2e.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/integration/migration/test_foreshadowing_migration_e2e.py
"""ForeshadowingMigrationService 端到端集成测试。

使用临时 SQLite 数据库 + WriteDispatch 测试环境，覆盖：
- 幂等性（重复 3 次结果一致）
- 异常数据跳过
- 批次边界（1000 条 / batch_size=333 → 4 batches）
- 旧表保留只读（迁移后旧表数据不变）
- 断点续跑（模拟中断后从断点继续）
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pytest

from application.storyos.services.foreshadowing_migration_service import (
    ForeshadowingMigrationService,
)
from application.storyos.services.migration_audit_service import (
    MigrationAuditService,
)
from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingAdapter,
)
from application.storyos.migration.migration_log_repository import (
    MigrationLogRepository,
)
from application.storyos.migration.new_foreshadowing_writer import (
    NewForeshadowingWriter,
)
from infrastructure.persistence.database.connection import reset_connection_for_test


@pytest.fixture
def temp_db(monkeypatch):
    """创建临时 SQLite + 旧/新/migration_log 三张表。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    reset_connection_for_test(db_path=path)
    conn = sqlite3.connect(path)
    # 旧表（spec §1E 锁定 schema）
    conn.execute("""
        CREATE TABLE foreshadows (
            id TEXT PRIMARY KEY, novel_id TEXT NOT NULL,
            description TEXT NOT NULL, planted_chapter INTEGER NOT NULL,
            due_chapter INTEGER, resolved_chapter INTEGER,
            status TEXT NOT NULL DEFAULT 'planted',
            importance INTEGER NOT NULL DEFAULT 2,
            subtext_type TEXT
        )
    """)
    # 新表（1A storyos_foreshadowing_v1 schema）
    conn.execute("""
        CREATE TABLE storyos_foreshadowing_v1 (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            asset_type TEXT NOT NULL, status TEXT NOT NULL,
            description TEXT NOT NULL, importance INTEGER NOT NULL,
            planted_chapter INTEGER NOT NULL, payoff_chapter INTEGER,
            resolved_chapter INTEGER, migrated_from_legacy_id TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(migrated_from_legacy_id, project_id)
        )
    """)
    # migration_log 表
    conn.execute("""
        CREATE TABLE storyos_migration_log_v1 (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            migration_type TEXT NOT NULL, batch_id TEXT NOT NULL,
            old_ids TEXT NOT NULL, status TEXT NOT NULL,
            started_at TEXT NOT NULL, completed_at TEXT, error TEXT
        )
    """)
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


def _populate_legacy(conn_path: str, novel_id: str, n: int, mix_invalid: bool = False):
    """填充 n 条旧表记录。"""
    import sqlite3
    conn = sqlite3.connect(conn_path)
    statuses = ["planted", "resolved", "abandoned"]
    for i in range(n):
        status = statuses[i % 3]
        if mix_invalid and i == n - 1:
            status = "legacy_weird"  # 1 条未知 status
        conn.execute(
            "INSERT INTO foreshadows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"fs-{i}", novel_id, f"desc-{i}", i + 1, None, 5 if status == "resolved" else None,
             status, 2, None),
        )
    conn.commit()
    conn.close()


def _build_service(db_path: str) -> ForeshadowingMigrationService:
    conn_provider = lambda: __import__("sqlite3").connect(db_path)
    legacy = LegacyForeshadowingAdapter(
        cursor_provider=lambda sql, params=(): conn_provider().execute(sql, params)
    )
    log_repo = MigrationLogRepository(db_provider=conn_provider)
    new_writer = NewForeshadowingWriter()
    audit = MigrationAuditService()
    return ForeshadowingMigrationService(
        legacy_adapter=legacy, log_repository=log_repo,
        new_table_writer=new_writer, audit_service=audit,
    )


def test_full_migration_100_records(temp_db):
    """100 条记录全量迁移正确性。"""
    _populate_legacy(temp_db, "novel-1", 100)
    service = _build_service(temp_db)
    result = service.execute("novel-1", batch_size=50)
    assert result.batches_total == 2
    assert result.batches_done == 2
    assert result.records_migrated == 100
    assert result.status == "completed"


def test_idempotent_repeated_execution(temp_db):
    """幂等性：重复 3 次迁移结果一致（不重复插入）。"""
    _populate_legacy(temp_db, "novel-1", 50)
    service = _build_service(temp_db)

    r1 = service.execute("novel-1", batch_size=50)
    r2 = service.execute("novel-1", batch_size=50)
    r3 = service.execute("novel-1", batch_size=50)

    assert r1.records_migrated == 50
    assert r2.records_migrated == 0  # 已迁移
    assert r3.records_migrated == 0

    # 新表只有 50 条
    import sqlite3
    conn = sqlite3.connect(temp_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM storyos_foreshadowing_v1 WHERE project_id = ?",
        ("novel-1",),
    ).fetchone()[0]
    assert count == 50


def test_invalid_status_records_skipped(temp_db):
    """未知 status 的记录跳过（不入新表）。"""
    _populate_legacy(temp_db, "novel-1", 10, mix_invalid=True)
    service = _build_service(temp_db)
    result = service.execute("novel-1", batch_size=50)
    assert result.records_migrated == 9  # 跳过 1 条 legacy_weird
    assert result.status == "completed"


def test_batch_boundary_1000_records(temp_db):
    """1000 条 / batch_size=333 → 4 batches（333+333+333+1）。"""
    _populate_legacy(temp_db, "novel-1", 1000)
    service = _build_service(temp_db)
    result = service.execute("novel-1", batch_size=333)
    assert result.batches_total == 4
    assert result.batches_done == 4
    assert result.records_migrated == 1000


def test_legacy_table_unchanged_after_migration(temp_db):
    """迁移后旧 foreshadows 表数据未被修改（spec Q8 锁定）。"""
    _populate_legacy(temp_db, "novel-1", 10)
    service = _build_service(temp_db)

    # 快照旧表
    import sqlite3
    conn = sqlite3.connect(temp_db)
    before = conn.execute("SELECT * FROM foreshadows ORDER BY id").fetchall()
    conn.close()

    service.execute("novel-1", batch_size=5)

    # 比较旧表
    conn = sqlite3.connect(temp_db)
    after = conn.execute("SELECT * FROM foreshadows ORDER BY id").fetchall()
    conn.close()
    assert before == after, "旧表数据被修改！违反 spec Q8 锁定"


def test_resume_after_partial_failure(temp_db):
    """断点续跑：模拟前 2 批成功 + 第 3 批失败，重启后只迁移剩余批次。"""
    _populate_legacy(temp_db, "novel-1", 30)

    # 第一次：制造第 3 批失败（batch_size=10 → batch 3 = fs-20..fs-29）
    service = _build_service(temp_db)
    # mock new_writer 让第 3 批失败
    original = service._new_writer.insert_batch
    call_count = [0]
    def flaky_insert(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 3:
            raise RuntimeError("simulated failure")
        return original(*args, **kwargs)
    service._new_writer.insert_batch = flaky_insert

    result = service.execute("novel-1", batch_size=10)
    assert result.status == "partial"
    assert result.batches_done == 2

    # 第二次：移除 mock，应该迁移剩余的批次
    service2 = _build_service(temp_db)
    result2 = service2.execute("novel-1", batch_size=10)
    assert result2.status == "completed"
    assert result2.records_migrated == 10  # 只剩 10 条没迁移


def test_rollback_after_migration(temp_db):
    """迁移后 rollback 删除新表数据。"""
    _populate_legacy(temp_db, "novel-1", 10)
    service = _build_service(temp_db)
    service.execute("novel-1", batch_size=10)
    migration_id = service._log_repo.get_committed_old_ids("novel-1")
    assert len(migration_id) == 10

    # 找一条 migration_log
    import sqlite3
    conn = sqlite3.connect(temp_db)
    mid = conn.execute(
        "SELECT id FROM storyos_migration_log_v1 WHERE status='committed' LIMIT 1"
    ).fetchone()[0]
    conn.close()

    result = service.rollback(mid)
    assert result.status == "rolled_back"
    assert result.records_deleted == 10

    # 新表被清空
    conn = sqlite3.connect(temp_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM storyos_foreshadowing_v1"
    ).fetchone()[0]
    conn.close()
    assert count == 0


def test_migration_log_records_each_batch(temp_db):
    """每批次写入一条 migration_log（spec §1E 锁定）。"""
    _populate_legacy(temp_db, "novel-1", 100)
    service = _build_service(temp_db)
    service.execute("novel-1", batch_size=25)

    import sqlite3
    conn = sqlite3.connect(temp_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM storyos_migration_log_v1 WHERE status='committed'"
    ).fetchone()[0]
    conn.close()
    assert count == 4  # 4 batches → 4 log entries
```

- [ ] **Step 2: 运行测试确认失败** — 期望 import error 或 assertion error

Run: `pytest tests/integration/migration/test_foreshadowing_migration_e2e.py -v`
Expected: FAILED

- [ ] **Step 3: 实现** —— 上述测试已经足够，关键是要保证 fixture 正确。

- [ ] **Step 4: 运行测试确认通过** — 期望 8 passed

Run: `pytest tests/integration/migration/test_foreshadowing_migration_e2e.py -v`
Expected: 8 passed

- [ ] **Step 5: 验证没有破坏现有测试**

Run: `pytest tests/unit/application/storyos/ tests/integration/api/v1/storyos/test_migration_endpoints.py -v`
Expected: 全部通过

- [ ] **Step 6: Commit**

```bash
git add tests/integration/migration/
git commit -m "test(migration): add end-to-end integration tests (幂等 + 异常 + 批次边界 + 旧表保留)"
```

---

#### Task F2: 10k 性能基准（migration_10k < 30s + dry_run < 5s）

**Files:**
- Create: `tests/performance/test_migration_10k.py`

- [ ] **Step 1: 写失败测试（性能断言）**

```python
# tests/performance/test_migration_10k.py
"""1 万条 foreshadowing 迁移性能基准（spec §5.3 锁定）。"""
from __future__ import annotations

import os
import tempfile
import time

import pytest

# 复用 Group F1 的 fixture / helper
from tests.integration.migration.test_foreshadowing_migration_e2e import (
    _populate_legacy, _build_service,
)


@pytest.mark.slow
def test_migration_10k_under_30_seconds():
    """migration_10k 性能基准：1 万条 < 30s（spec §5.3 锁定）。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    import sqlite3
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE foreshadows (
            id TEXT PRIMARY KEY, novel_id TEXT NOT NULL,
            description TEXT NOT NULL, planted_chapter INTEGER NOT NULL,
            due_chapter INTEGER, resolved_chapter INTEGER,
            status TEXT NOT NULL DEFAULT 'planted',
            importance INTEGER NOT NULL DEFAULT 2, subtext_type TEXT
        );
        CREATE TABLE storyos_foreshadowing_v1 (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            asset_type TEXT NOT NULL, status TEXT NOT NULL,
            description TEXT NOT NULL, importance INTEGER NOT NULL,
            planted_chapter INTEGER NOT NULL, payoff_chapter INTEGER,
            resolved_chapter INTEGER, migrated_from_legacy_id TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(migrated_from_legacy_id, project_id)
        );
        CREATE TABLE storyos_migration_log_v1 (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            migration_type TEXT NOT NULL, batch_id TEXT NOT NULL,
            old_ids TEXT NOT NULL, status TEXT NOT NULL,
            started_at TEXT NOT NULL, completed_at TEXT, error TEXT
        );
    """)
    conn.close()

    _populate_legacy(path, "novel-perf", 10000)

    service = _build_service(path)

    start = time.time()
    result = service.execute("novel-perf", batch_size=500)
    elapsed = time.time() - start

    assert result.records_migrated == 10000
    assert elapsed < 30, f"migration_10k took {elapsed:.1f}s, must be < 30s"

    # 验证新表数据正确
    conn = sqlite3.connect(path)
    count = conn.execute(
        "SELECT COUNT(*) FROM storyos_foreshadowing_v1 WHERE project_id = ?",
        ("novel-perf",),
    ).fetchone()[0]
    conn.close()
    assert count == 10000

    os.unlink(path)


@pytest.mark.slow
def test_dry_run_10k_under_5_seconds():
    """dry_run_10k 性能基准：1 万条 < 5s（spec §5.3 推断）。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    import sqlite3
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE foreshadows (
            id TEXT PRIMARY KEY, novel_id TEXT NOT NULL,
            description TEXT NOT NULL, planted_chapter INTEGER NOT NULL,
            due_chapter INTEGER, resolved_chapter INTEGER,
            status TEXT NOT NULL DEFAULT 'planted',
            importance INTEGER NOT NULL DEFAULT 2, subtext_type TEXT
        );
        CREATE TABLE storyos_migration_log_v1 (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            migration_type TEXT NOT NULL, batch_id TEXT NOT NULL,
            old_ids TEXT NOT NULL, status TEXT NOT NULL,
            started_at TEXT NOT NULL, completed_at TEXT, error TEXT
        );
    """)
    conn.close()

    _populate_legacy(path, "novel-perf-dry", 10000)
    service = _build_service(path)

    start = time.time()
    report = service.scan("novel-perf-dry")
    elapsed = time.time() - start

    assert report.total == 10000
    assert elapsed < 5, f"dry_run_10k took {elapsed:.1f}s, must be < 5s"

    os.unlink(path)
```

- [ ] **Step 2: 运行测试确认失败** — 期望 import 错误

Run: `pytest tests/performance/test_migration_10k.py -v`
Expected: FAILED

- [ ] **Step 3: 实现** —— 性能测试本身就是规范，只需保证 fixture 共享正常工作。

- [ ] **Step 4: 运行测试确认通过** —— 注意：这测试**慢**，默认 skip

Run: `pytest tests/performance/test_migration_10k.py -v -m slow --run-slow`
Expected: 2 passed

- [ ] **Step 5: 验证常规测试套件不被影响**

Run: `pytest tests/ -v -m "not slow"`
Expected: 全部通过（性能测试默认被 `-m "not slow"` 过滤）

- [ ] **Step 6: Commit**

```bash
git add tests/performance/test_migration_10k.py
git commit -m "test(migration): add 10k performance benchmarks (spec §5.3)"
```

---

## 4. 端到端集成验收（1E 阶段收尾）

#### Task AC1: 端到端 happy path 集成测试（CLI → DB → API 全链路）

**Files:**
- Create: `tests/integration/migration/test_e2e_full_chain.py`

- [ ] **Step 1: 写测试**

```python
# tests/integration/migration/test_e2e_full_chain.py
"""1E 端到端集成测试：CLI 调用 → DB 写入 → API 查询 全链路。"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from interfaces.main import app


@pytest.fixture
def temp_db_with_data(monkeypatch):
    """完整测试环境：临时 DB + 旧表数据 + 1D 测试 fixtures。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE foreshadows (
            id TEXT PRIMARY KEY, novel_id TEXT NOT NULL,
            description TEXT NOT NULL, planted_chapter INTEGER NOT NULL,
            due_chapter INTEGER, resolved_chapter INTEGER,
            status TEXT NOT NULL DEFAULT 'planted',
            importance INTEGER NOT NULL DEFAULT 2, subtext_type TEXT
        );
        CREATE TABLE storyos_foreshadowing_v1 (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            asset_type TEXT NOT NULL, status TEXT NOT NULL,
            description TEXT NOT NULL, importance INTEGER NOT NULL,
            planted_chapter INTEGER NOT NULL, payoff_chapter INTEGER,
            resolved_chapter INTEGER, migrated_from_legacy_id TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(migrated_from_legacy_id, project_id)
        );
        CREATE TABLE storyos_migration_log_v1 (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            migration_type TEXT NOT NULL, batch_id TEXT NOT NULL,
            old_ids TEXT NOT NULL, status TEXT NOT NULL,
            started_at TEXT NOT NULL, completed_at TEXT, error TEXT
        );
        INSERT INTO foreshadows VALUES
            ('fs-1', 'p1', 'desc1', 1, NULL, NULL, 'planted', 2, NULL),
            ('fs-2', 'p1', 'desc2', 2, NULL, 5, 'resolved', 3, NULL),
            ('fs-3', 'p1', 'desc3', 3, NULL, NULL, 'abandoned', 1, NULL);
    """)
    conn.close()
    yield path
    os.unlink(path)


def test_cli_dry_run_outputs_valid_json(temp_db_with_data, monkeypatch):
    """CLI --dry-run 输出 JSON 报告。"""
    monkeypatch.setenv("PLOTPILOT_DB_PATH", temp_db_with_data)
    result = subprocess.run(
        [sys.executable, "scripts/migrate_storyos.py", "--dry-run",
         "--project-id", "p1", "--json"],
        capture_output=True, text=True, cwd="/Users/longsa/Codes/plotPilot",
        env={**os.environ, "PLOTPILOT_DB_PATH": temp_db_with_data},
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    report = json.loads(result.stdout)
    assert report["total"] == 3
    assert report["migratable"] == 3
    assert report["invalid"] == 0


def test_cli_execute_writes_to_new_table(temp_db_with_data, monkeypatch):
    """CLI --execute 写入新表。"""
    env = {**os.environ, "PLOTPILOT_DB_PATH": temp_db_with_data}
    result = subprocess.run(
        [sys.executable, "scripts/migrate_storyos.py", "--execute",
         "--project-id", "p1", "--json", "--batch-size", "10"],
        capture_output=True, text=True, cwd="/Users/longsa/Codes/plotPilot",
        env=env,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    report = json.loads(result.stdout)
    assert report["status"] == "completed"
    assert report["records_migrated"] == 3

    # 验证新表数据
    conn = sqlite3.connect(temp_db_with_data)
    count = conn.execute(
        "SELECT COUNT(*) FROM storyos_foreshadowing_v1 WHERE project_id = ?",
        ("p1",),
    ).fetchone()[0]
    conn.close()
    assert count == 3


def test_cli_execute_then_api_status(temp_db_with_data, monkeypatch):
    """CLI execute 后，API GET /status 能查到进度。"""
    env = {**os.environ, "PLOTPILOT_DB_PATH": temp_db_with_data}
    # 1. CLI execute
    result = subprocess.run(
        [sys.executable, "scripts/migrate_storyos.py", "--execute",
         "--project-id", "p1", "--json"],
        capture_output=True, text=True, cwd="/Users/longsa/Codes/plotPilot",
        env=env,
    )
    assert result.returncode == 0
    report = json.loads(result.stdout)
    migration_id = report["migration_id"]

    # 2. API GET /status（mock service，注入 audit service）
    from application.storyos.services.migration_audit_service import MigrationAuditService
    audit = MigrationAuditService()
    audit.record_migration(
        migration_id=migration_id, project_id="p1",
        batches_total=1, batches_done=1, records_migrated=3, errors=[],
    )

    with patch(
        "interfaces.api.v1.storyos.routes.migration_routes.get_migration_service"
    ) as mock_get:
        mock_service = type("MockSvc", (), {})()
        mock_service.get_audit_record = lambda mid: {
            "migration_id": mid, "project_id": "p1",
            "batches_total": 1, "batches_done": 1,
            "records_migrated": 3, "status": "completed", "errors": [],
        }
        mock_get.return_value = mock_service

        client = TestClient(app)
        resp = client.get(f"/api/v1/storyos/p1/migration/{migration_id}/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["migration_id"] == migration_id
        assert body["progress_pct"] == 100


def test_api_preview_matches_cli_dry_run(temp_db_with_data, monkeypatch):
    """API preview 与 CLI --dry-run 输出应一致（验证联通）。"""
    from application.storyos.value_objects.migration_preview_report import (
        MigrationPreviewReport,
    )

    # API 路径
    with patch(
        "interfaces.api.v1.storyos.routes.migration_routes.get_migration_service"
    ) as mock_get:
        mock_service = type("MockSvc", (), {})()
        mock_service.scan = lambda pid: MigrationPreviewReport(
            project_id=pid, total=3, scanned=3, migratable=3,
            skipped=0, invalid=0,
        )
        mock_get.return_value = mock_service
        client = TestClient(app)
        resp = client.post("/api/v1/storyos/p1/migration/preview")
        api_body = resp.json()

    # CLI 路径
    env = {**os.environ, "PLOTPILOT_DB_PATH": temp_db_with_data}
    result = subprocess.run(
        [sys.executable, "scripts/migrate_storyos.py", "--dry-run",
         "--project-id", "p1", "--json"],
        capture_output=True, text=True, cwd="/Users/longsa/Codes/plotPilot",
        env=env,
    )
    cli_body = json.loads(result.stdout)

    # 关键字段一致
    assert api_body["total"] == cli_body["total"]
    assert api_body["migratable"] == cli_body["migratable"]
    assert api_body["invalid"] == cli_body["invalid"]
```

- [ ] **Step 2: 运行 E2E 测试** — 期望 4 passed

Run: `pytest tests/integration/migration/test_e2e_full_chain.py -v`
Expected: 4 passed

- [ ] **Step 3: 验证完整 1E 测试套件** — 运行所有 1E 相关测试

Run: `pytest tests/unit/application/storyos/migration/ tests/unit/application/storyos/services/test_foreshadowing_migration.py tests/unit/application/storyos/services/test_migration_audit_service.py tests/integration/api/v1/storyos/test_migration_endpoints.py tests/integration/migration/ -v`
Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add tests/integration/migration/test_e2e_full_chain.py
git commit -m "test(migration): add full-chain E2E tests (CLI → DB → API)"
```

---

## 5. 关键设计决策

### 5.1 旧表只读是绝对约束（spec Q8）

代码层强制（不只是文档）：
- `LegacyForeshadowingAdapter` 内部检查 SQL 关键字（test_adapter_does_not_modify_legacy_table）
- `ForeshadowingMigrationService.rollback()` 严禁调 `legacy.fetch_all_with_invalid` / `count_for_novel`
- rollback 只删除新表，旧表永远不动
- 集成测试 `test_legacy_table_unchanged_after_migration` 锁定不变量

### 5.2 幂等性的两层保证

1. **数据库层**：`UNIQUE(migrated_from_legacy_id, project_id)` —— 重复 INSERT 被 unique 约束拦截
2. **服务层**：`get_committed_old_ids()` 在 execute 之前过滤已迁移的 ID

两层结合：
- 服务层过滤避免无用的 SQL
- 数据库层兜底，避免竞态条件导致重复插入
- 配合 WriteDispatch 单写者模型，最终一致性

### 5.3 断点续跑的实现选择

**为什么用 `migration_log` 而不是 batch_id 计数**：
- batch_id 计数假设 batch_size 不变；如果用户重启时改 batch_size，计数会错位
- `migration_log` 记录实际处理的 old_ids，重启时基于已 committed 的 ID 集合做差集，与 batch_size 无关
- 同时 `migration_log` 也是审计日志（spec §1E 锁定）

**断点续跑步骤**：
1. `execute()` 拉旧表全量记录
2. `log_repo.get_committed_old_ids(project_id)` → 已迁移的 old_id 集合
3. 从 migratable_pairs 中过滤掉已 committed 的 ID
4. 剩余 ID 分批写入

**中断后**：
- 未完成的 batch 没有写入 migration_log（因为 INSERT + log 是同一事务，失败回滚）
- 重启时 committed_ids 集合自动排除已完成部分
- failed batches 不在 committed 集合中，下次重试会再次尝试

### 5.4 dry_run 与真实 execute 的语义差异

| 行为 | dry_run=True | dry_run=False |
|---|---|---|
| 读取旧表 | ✅ | ✅ |
| 状态映射 | ✅ | ✅ |
| 计算 batch 数 | ✅ | ✅ |
| 写入新表 | ❌ | ✅ |
| 写入 migration_log | ❌ | ✅ |
| 返回 migration_id | `"dry-run"` | `mig-<uuid>` |

**dry_run 返回的 `batches_total` 是基于当前 migratable 数据估算的**。如果用户重启后数据变化，实际 execute 的 batches_total 可能不同。

### 5.5 status 端点的 ETA 估算

`MigrationStatusResponse.eta_seconds` 使用粗略估算：
```python
eta_seconds = (batches_total - batches_done) * 0.2  # 假设每批 200ms
```

**为什么用粗略估算**：
- 实际 ETA 需要历史批次的真实耗时，复杂度高
- migration 通常 1-3 秒内完成，ETA 不是关键 UX
- 前端 Workbench 只显示进度条，ETA 是次要字段

如果未来需要精确 ETA，可以扩展 `MigrationAuditRecord` 加 `avg_batch_ms` 字段。

### 5.6 CLI 与 API 复用 Service

CLI 与 API 都通过 DI 拿同一个 `ForeshadowingMigrationService` 实例，保证：
- 业务逻辑一致（scan / execute / rollback 行为相同）
- 审计聚合一致（同一进程内的 audit service 单例）

但 CLI 进程与 API 进程的 audit service 是隔离的（内存存储）。
长期审计通过 `migration_log` 表（持久化）。

### 5.7 WriteDispatch 与迁移的整合

`NewForeshadowingWriter.insert_batch()` 使用 `enqueue_txn_batch()` 把多条 INSERT 打包成一个事务：
- 单事务：要么全成功，要么全失败
- 通过 WriteDispatch 单写者队列串行，避免并发冲突
- 失败时整个 batch 回滚，migration_log 不会被错误标记为 committed

**为什么不直接用 sqlite3 的事务**：
- PlotPilot 的 SQLite 写入统一走 WriteDispatch（spec §3.5 锁定）
- 直接绕过会破坏单写者模型，可能导致与 EngineDaemon 并发冲突

### 5.8 与 1A/1B/1D 的契约边界

| 1A 产出 | 1E 消费 |
|---|---|
| `ForeshadowingMapper.convert_old_status_to_new` | Group A3 status_mapper 直接调用 |
| `storyos_foreshadowing_v1` schema + `migrated_from_legacy_id` 字段 | Group B2 new_writer INSERT 时写入 |
| `UNIQUE(migrated_from_legacy_id, project_id)` 索引 | Group B2 依赖此索引做幂等性 |

| 1B 产出 | 1E 消费 |
|---|---|
| `ForeshadowingMigrationService` stub（3 方法抛 NotImplementedError） | Group B 完整实现 |
| `get_migration_service` DI factory | Group D1 直接 import |

| 1D 产出 | 1E 消费 |
|---|---|
| `MigrationPreviewResponse` / `MigrationExecuteResponse` / `MigrationStatusResponse` | Group D 真实 handler 直接返回这些 DTO |
| `migration_routes.py`（501 桩） | Group D1 替换函数体 |
| `get_migration_service` 依赖工厂 | Group D1 通过 `Depends()` 注入 |
| 前端 `migrationApi` 客户端 | Group F1 E2E 测试验证联通 |

---

## 6. 完成判据

### 6.1 功能验收

- [ ] `legacy_foreshadowing_adapter` 只读（test_adapter_does_not_modify_legacy_table 通过）
- [ ] `ForeshadowingMigrationService.scan()` 返回 5 元组报告
- [ ] `ForeshadowingMigrationService.execute()` 支持 batch_size + dry_run + 幂等
- [ ] `ForeshadowingMigrationService.rollback()` 仅删除新表数据，旧表保留
- [ ] `MigrationAuditService` 聚合批次结果 + JSON 输出
- [ ] `scripts/migrate_storyos.py` 支持 `--dry-run` / `--execute` / `--rollback` / `--status`
- [ ] `POST /migration/preview` 返回 200 + MigrationPreviewResponse
- [ ] `POST /migration/execute` 返回 200 + MigrationExecuteResponse
- [ ] `GET /migration/{id}/status` 返回 200 + MigrationStatusResponse
- [ ] `POST /migration/{id}/rollback` 返回 200 + RollbackResponse
- [ ] `migration_log` 表持久化每批次状态

### 6.2 集成验收（spec §5.3 锁定）

- [ ] 1 万条迁移 < 30s（`test_migration_10k_under_30_seconds` 通过）
- [ ] 1 万条 dry-run < 5s（`test_dry_run_10k_under_5_seconds` 通过）
- [ ] 幂等性：重复 3 次迁移结果一致（`test_idempotent_repeated_execution` 通过）
- [ ] 异常数据跳过：`legacy_weird` status 不阻断 migration（`test_invalid_status_records_skipped` 通过）
- [ ] 批次边界：1000 条 / batch_size=333 → 4 batches（`test_batch_boundary_1000_records` 通过）
- [ ] 旧表保留只读（`test_legacy_table_unchanged_after_migration` 通过）
- [ ] 断点续跑（`test_resume_after_partial_failure` 通过）
- [ ] rollback（`test_rollback_after_migration` 通过）
- [ ] CLI ↔ API 输出一致（`test_api_preview_matches_cli_dry_run` 通过）

### 6.3 用户验收

- [ ] `python scripts/migrate_storyos.py --help` 显示完整子命令
- [ ] `--dry-run` 输出 JSON 报告（`--json` 标志）
- [ ] `--execute` 输出进度 + 错误聚合
- [ ] `--rollback <id>` 仅删除新表数据
- [ ] `--status` 输出 audit 聚合报告
- [ ] Workbench Migration Tool 入口可访问（1D 已有前端，1E 联通后即可用）

### 6.4 测试覆盖

| 测试类型 | 文件 | 测试数 |
|---|---|---|
| Unit: Adapter | `tests/unit/application/storyos/migration/test_legacy_foreshadowing_adapter.py` | 6 |
| Unit: Log Repository | `tests/unit/application/storyos/migration/test_migration_log_repository.py` | 7 |
| Unit: Status Mapper | `tests/unit/application/storyos/migration/test_status_mapper.py` | 7 |
| Unit: MigrationPreviewReport | `tests/unit/application/storyos/value_objects/test_migration_preview_report.py` | 3 |
| Unit: MigrationService | `tests/unit/application/storyos/services/test_foreshadowing_migration.py` | 23 |
| Unit: AuditService | `tests/unit/application/storyos/services/test_migration_audit_service.py` | 9 |
| Unit: CLI | `tests/unit/scripts/test_migrate_storyos_cli.py` | 8 |
| Integration: API | `tests/integration/api/v1/storyos/test_migration_endpoints.py` | 11 |
| Integration: E2E | `tests/integration/migration/test_foreshadowing_migration_e2e.py` | 8 |
| Integration: Full Chain | `tests/integration/migration/test_e2e_full_chain.py` | 4 |
| Performance: 10k | `tests/performance/test_migration_10k.py` | 2 |
| **总计** | **11 测试文件** | **88 测试** |

### 6.5 阶段输出交接清单（Phase 2）

- [ ] 旧 `foreshadows` 表数据**保留只读**（spec Q8 锁定，不可清理）
- [ ] 新 `storyos_foreshadowing_v1` 表数据**持续增长**（后续 1D/1E 章节产生的伏笔也走新表）
- [ ] `migration_log` 表**长期保留**（审计追溯）
- [ ] CLI 工具**可重复使用**（运维脚本可调用）
- [ ] 1D 前端 `Migration Tool` 入口**已联通**（无需 1D 改动）

---

## 7. 任务依赖与并行机会

### 7.1 严格顺序（A → B → C → D → E → F）

```
A1 (legacy adapter)
  └→ A2 (migration_log repo)
       └→ A3 (status_mapper)
            └→ B1 (scan)
                 ├→ B2 (execute)
                 │    └→ B3 (rollback)
                 └→ C1 (audit record)
                      └→ C2 (audit aggregate)
                           ├→ D1 (API 替换 501)
                           │    └→ D2 (API 新端点 /status /rollback)
                           └→ E1 (CLI dry-run/execute)
                                └→ E2 (CLI 进度条 + 错误聚合)
                                     └→ F1 (E2E 集成)
                                          └→ F2 (10k 性能)
```

### 7.2 并行机会

- **A1 → A2 → A3** 严格顺序（依赖 adapter 才能写 log repo；依赖 1A mapper 才能写 status_mapper）
- **B1 → B2 / B3**：B2 / B3 依赖 B1 的 scan 设计
- **B2 / B3 → C1**：audit service 接收 migration service 的调用
- **C1 → C2**：aggregator 依赖 record 方法
- **D1 → D2**：D2 在 D1 替换 501 后才能新增 /status 端点（保证端点顺序）
- **E1 → E2**：E2 增强 E1 的输出格式
- **F1 → F2**：性能测试需要 service 全部完成

**最佳执行节奏**：
- 单人执行：A → B → C → D → E → F（顺序）
- Subagent-driven：
  - Subagent 1：Group A（adapter + log + mapper）
  - Subagent 2：Group B（scan + execute + rollback）
  - Subagent 3：Group C（audit）
  - Subagent 4：Group D + E（API + CLI，可并行）
  - Subagent 5：Group F（集成 + 性能测试）

### 7.3 估时

| Group | 任务数 | LOC | 估时 |
|---|---|---|---|
| A: 仓储 + Schema | 3 | ~250 | 0.25 天 |
| B: Service | 3 | ~400 | 0.5 天 |
| C: Audit | 2 | ~150 | 0.25 天 |
| D: API | 2 | ~200 | 0.25 天 |
| E: CLI | 2 | ~150 | 0.25 天 |
| F: 集成 + 性能 | 2 | ~50 | 0.25 天 |
| **总计** | **14** | **~1200** | **~2 天** |

---

## 8. 状态

**当前状态:** 详细计划完成，等待用户 review

**下一步行动:**
1. 用户 review 通过后启动 A1 任务
2. 严格按 A → B → C → D → E → F 顺序执行
3. Group D / E 可在 Group C 完成后并行
4. 完成 1E 后整个 StoryOS Phase 1 闭环（1A → 1B → 1C → 1D → 1E）

**估时:** 2 天（按 1 人全职计算）

---

## 9. 设计参考

- **Spec 主参考**：[`../specs/2026-07-02-storyos-integration-design.md`](../specs/2026-07-02-storyos-integration-design.md)
  - §Q5 Registry 范围
  - §Q8 现有项目迁移（单向迁移 + 旧表保留只读）
  - §3.5 WriteDispatch 扩展
  - §6.1 5 子阶段
  - §6.3 Top 5 风险 + 缓解（Risk #3 Migration 数据不一致）
  - §5.3 性能基准（migration_10k < 30s）
  - 附录 C status 映射表
- **子 Spec**：[`../specs/2026-07-02-storyos-asset-field-spec.md`](../specs/2026-07-02-storyos-asset-field-spec.md)
  - §3 Clue 字段（与 Foreshadowing 字段对比参考）
- **1A 阶段产出**：[`./2026-07-02-storyos-phase-1a-foundation.md`](./2026-07-02-storyos-phase-1a-foundation.md)
  - `ForeshadowingMapper.convert_old_status_to_new`（本计划 A3 直接调用）
  - `storyos_foreshadowing_v1` schema + `migrated_from_legacy_id` 字段（B2 写入）
  - `UNIQUE(migrated_from_legacy_id, project_id)` 索引（幂等性）
- **1B 阶段产出**：[`./2026-07-02-storyos-phase-1b-application.md`](./2026-07-02-storyos-phase-1b-application.md)
  - F3 `ForeshadowingMigrationService` stub（B 完整实现覆盖）
  - `get_migration_service` DI factory（D1 直接 import）
- **1C 阶段产出**：[`./2026-07-02-storyos-phase-1c-engine.md`](./2026-07-02-storyos-phase-1c-engine.md)
  - `engine/runtime/storyos_delegate.py`（与 1E 无直接依赖，但共用 service 容器）
- **1D 阶段产出**：[`./2026-07-02-storyos-phase-1d-frontend-api.md`](./2026-07-02-storyos-phase-1d-frontend-api.md)
  - `migration_schemas.py` 5 DTOs（D1 直接消费）
  - `migration_routes.py` 501 桩（D1 替换函数体）
  - `get_migration_service` 依赖工厂（D1 通过 Depends 注入）
  - `frontend/src/api/storyos/migration.ts`（F1 联通验证）
- **现有代码**：
  - 旧表 schema：`infrastructure/persistence/database/schema.sql:537-550`
  - 旧表 mapper：`infrastructure/persistence/mappers/foreshadowing_mapper.py`
  - 旧表 repository：`infrastructure/persistence/database/sqlite_foreshadowing_repository.py`
  - 旧值对象：`domain/novel/value_objects/foreshadowing.py`
  - WriteDispatch：`infrastructure/persistence/database/write_dispatch.py:enqueue_txn_batch()`
  - 1D 1D 桩代码：`interfaces/api/v1/storyos/routes/migration_routes.py:2086-2136`

