from domain.storyos.contracts import CascadeTrigger


def test_cascade_trigger_has_6_members():
    assert len(CascadeTrigger) == 6


def test_cascade_trigger_member_names():
    expected = {
        "MYSTERY_REVEALED", "TWIST_REVEALED", "REVEAL_REVEALED",
        "PROMISE_FULFILLED", "CONFLICT_RESOLVED", "CONFLICT_ESCALATED",
    }
    assert {m.name for m in CascadeTrigger} == expected


def test_conflict_escalated_exists():
    assert CascadeTrigger.CONFLICT_ESCALATED.value == "conflict_escalated"