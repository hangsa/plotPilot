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