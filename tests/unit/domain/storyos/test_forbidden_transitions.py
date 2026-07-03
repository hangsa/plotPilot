"""FORBIDDEN_TRANSITIONS + is_forbidden_transition contract tests (Task A4)."""
import pytest

from domain.storyos.contracts import (
    AssetStatus,
    FORBIDDEN_TRANSITIONS,
    is_forbidden_transition,
)


def test_forbidden_transitions_count():
    assert len(FORBIDDEN_TRANSITIONS) == 8


def test_forbidden_transitions_contents():
    expected = {
        (AssetStatus.RESOLVED, AssetStatus.ACTIVE),
        (AssetStatus.FULFILLED, AssetStatus.ACTIVE),
        (AssetStatus.REVEALED, AssetStatus.HIDDEN),
        (AssetStatus.DEAD, AssetStatus.ACTIVE),
        (AssetStatus.ABANDONED, AssetStatus.PLANTED),
        (AssetStatus.ABANDONED, AssetStatus.DEVELOPING),
        (AssetStatus.RESOLVED, AssetStatus.PLANTED),
        (AssetStatus.FULFILLED, AssetStatus.PLANTED),
    }
    assert FORBIDDEN_TRANSITIONS == expected


@pytest.mark.parametrize("src,dst,expected", [
    (AssetStatus.RESOLVED, AssetStatus.ACTIVE, True),
    (AssetStatus.ACTIVE, AssetStatus.RESOLVED, False),
    (AssetStatus.DEAD, AssetStatus.ACTIVE, True),
    (AssetStatus.ACTIVE, AssetStatus.PLANTED, False),
])
def test_is_forbidden_transition(src, dst, expected):
    assert is_forbidden_transition(src, dst) is expected


def test_is_forbidden_transition_type_validation():
    with pytest.raises(TypeError):
        is_forbidden_transition("active", AssetStatus.ACTIVE)
