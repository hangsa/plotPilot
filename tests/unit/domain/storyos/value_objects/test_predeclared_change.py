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
