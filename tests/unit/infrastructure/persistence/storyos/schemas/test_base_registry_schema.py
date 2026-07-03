from sqlalchemy.orm import declarative_base

from infrastructure.persistence.storyos.schemas.base import BaseRegistrySchema


def _make_concrete_registry_table():
    """Compose the mixin with a minimal concrete class so __table__ exists.

    SQLAlchemy 2.0 mixins only become mapped (and produce __table__) when
    combined with a class that has its own __tablename__ under a declarative
    registry. This helper exists purely to let the test introspect columns.
    """
    Base = declarative_base()

    class _ConcreteRegistry(Base, BaseRegistrySchema):
        __tablename__ = "_test_concrete_registry_for_mixin"

    return _ConcreteRegistry


def test_base_registry_schema_fields():
    """验证 mixin 定义了 9 个共用字段。"""
    expected_fields = {
        "id", "project_id", "created_chapter", "status",
        "description", "linked_assets",
        "cascade_updated_at", "created_at", "updated_at",
    }
    concrete = _make_concrete_registry_table()
    actual = {c.name for c in concrete.__table__.columns}
    assert expected_fields.issubset(actual), f"missing: {expected_fields - actual}"


def test_base_registry_schema_no_tablename():
    """BaseRegistrySchema 是 mixin，不设置 __tablename__。"""
    assert not hasattr(BaseRegistrySchema, "__tablename__") or BaseRegistrySchema.__tablename__ is None