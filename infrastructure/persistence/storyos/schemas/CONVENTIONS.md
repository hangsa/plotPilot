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

## Schema 类继承模式

- 每个 schema 必须 **同时** 继承 `BaseRegistrySchema` 和共享的 `Base`（声明自 `infrastructure/persistence/storyos/schemas/base.py`）

```python
from infrastructure.persistence.storyos.schemas.base import Base, BaseRegistrySchema

class MysterySchema(BaseRegistrySchema, Base):
    __tablename__ = "storyos_mystery_v1"
    clues: Mapped[list[dict]] = mapped_column(JSON, default=list)
```

- **不要**直接继承 `DeclarativeBase` —— SQLAlchemy 2.0 禁止把 `DeclarativeBase` 自身作为多重基类使用，会抛 `InvalidRequestError`
- `BaseRegistrySchema` 是 **mixin**（提供 9 个共用字段），不带 `__tablename__`
- `Base` 是 **共享 declarative 基类**（所有 11 张 storyos 表共用同一 registry）
