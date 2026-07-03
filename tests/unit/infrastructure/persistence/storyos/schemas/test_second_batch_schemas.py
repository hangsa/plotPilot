from infrastructure.persistence.storyos.schemas.base import BaseRegistrySchema
from infrastructure.persistence.storyos.schemas.reveal_schema import RevealSchema
from infrastructure.persistence.storyos.schemas.expectation_schema import ExpectationSchema
from infrastructure.persistence.storyos.schemas.goal_schema import GoalSchema
from infrastructure.persistence.storyos.schemas.foreshadowing_schema import ForeshadowingSchema


def test_reveal_schema_tablename():
    assert RevealSchema.__tablename__ == "storyos_reveal_v1"


def test_expectation_schema_tablename():
    assert ExpectationSchema.__tablename__ == "storyos_expectation_v1"


def test_goal_schema_tablename():
    assert GoalSchema.__tablename__ == "storyos_goal_v1"


def test_foreshadowing_schema_tablename():
    assert ForeshadowingSchema.__tablename__ == "storyos_foreshadowing_v1"


def test_all_schemas_inherit_base():
    for cls in (RevealSchema, ExpectationSchema, GoalSchema, ForeshadowingSchema):
        assert issubclass(cls, BaseRegistrySchema)


def test_reveal_has_related_and_revealed():
    cols = {c.name for c in RevealSchema.__table__.columns}
    assert "related_mystery" in cols
    assert "revealed_in_chapter" in cols
    assert "linked_to_conflict" in cols


def test_expectation_has_intensity():
    cols = {c.name for c in ExpectationSchema.__table__.columns}
    assert "intensity" in cols


def test_goal_has_current_progress():
    cols = {c.name for c in GoalSchema.__table__.columns}
    assert "current_progress" in cols


def test_foreshadowing_has_planted_and_resolved():
    cols = {c.name for c in ForeshadowingSchema.__table__.columns}
    assert "planted_in_chapter" in cols
    assert "importance" in cols
    assert "resolved_in_chapter" in cols
    assert "suggested_resolve_chapter" in cols