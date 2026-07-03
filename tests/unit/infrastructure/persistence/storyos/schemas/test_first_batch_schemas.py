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