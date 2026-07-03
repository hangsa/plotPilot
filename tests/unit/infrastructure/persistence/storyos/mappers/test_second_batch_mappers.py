import pytest

from domain.novel.value_objects.foreshadowing import ImportanceLevel
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.expectation import Expectation
from domain.storyos.entities.foreshadowing import Foreshadowing
from domain.storyos.entities.goal import Goal, ProgressMarker
from domain.storyos.entities.reveal import Reveal
from infrastructure.persistence.storyos.mappers.expectation_mapper import (
    ExpectationMapper,
)
from infrastructure.persistence.storyos.mappers.foreshadowing_mapper import (
    ForeshadowingMapper,
)
from infrastructure.persistence.storyos.mappers.goal_mapper import GoalMapper
from infrastructure.persistence.storyos.mappers.reveal_mapper import RevealMapper


def test_reveal_round_trip():
    r = Reveal(
        id="r1", novel_id="n1", content="the wizard is real",
        status=AssetStatus.HIDDEN, related_mystery="m1",
    )
    row = RevealMapper.to_orm(r)
    r2 = RevealMapper.to_domain(row)
    assert r2 == r


def test_reveal_round_trip_revealed():
    r = Reveal(
        id="r1", novel_id="n1", content="the wizard is real",
        status=AssetStatus.REVEALED, related_mystery="m1",
        revealed_in_chapter=10,
    )
    row = RevealMapper.to_orm(r)
    r2 = RevealMapper.to_domain(row)
    assert r2 == r


def test_expectation_round_trip():
    e = Expectation(
        id="e1", novel_id="n1", description="protagonist finds treasure",
        status=AssetStatus.ACTIVE, created_chapter=1, intensity=42,
    )
    row = ExpectationMapper.to_orm(e)
    e2 = ExpectationMapper.to_domain(row)
    assert e2 == e


def test_goal_round_trip():
    g = Goal(
        id="g1", novel_id="n1", description="reach the temple",
        status=AssetStatus.ACTIVE, created_chapter=1,
        current_progress=ProgressMarker.T3,
    )
    row = GoalMapper.to_orm(g)
    g2 = GoalMapper.to_domain(row)
    assert g2 == g


def test_foreshadowing_round_trip():
    f = Foreshadowing(
        id="f1", novel_id="n1", description="the scar",
        importance=ImportanceLevel.HIGH, status=AssetStatus.PLANTED,
        planted_in_chapter=2, suggested_resolve_chapter=20,
    )
    row = ForeshadowingMapper.to_orm(f)
    f2 = ForeshadowingMapper.to_domain(row)
    assert f2 == f


def test_convert_old_status_to_new_planted():
    assert ForeshadowingMapper.convert_old_status_to_new("planted") == AssetStatus.PLANTED


def test_convert_old_status_to_new_resolved():
    assert ForeshadowingMapper.convert_old_status_to_new("resolved") == AssetStatus.REVEALED


def test_convert_old_status_to_new_abandoned():
    assert ForeshadowingMapper.convert_old_status_to_new("abandoned") == AssetStatus.DEAD


def test_convert_old_status_to_new_unknown_raises():
    with pytest.raises(ValueError, match="Unknown old foreshadowing status"):
        ForeshadowingMapper.convert_old_status_to_new("unknown")