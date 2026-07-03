from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.twist import Twist, TwistType


def test_twist_type_has_6_values():
    assert len(TwistType) == 6
    expected = {
        "IDENTITY_REVEAL", "BETRAYAL", "FORTUNE_REVERSAL",
        "WORLD_RULE_REVEAL", "SACRIFICE", "TRUTH_REVEALED",
    }
    assert {m.name for m in TwistType} == expected


def test_twist_minimum_required():
    t = Twist(
        id="t1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=3,
        twist_type=TwistType.IDENTITY_REVEAL,
    )
    assert t.reveal_trigger is None
    assert t.forbidden_concurrent_twists == ()


def test_twist_with_reveal_trigger():
    t = Twist(
        id="t1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=3,
        twist_type=TwistType.TRUTH_REVEALED,
        reveal_trigger="mystery:m1:revealed",
    )
    assert t.reveal_trigger == "mystery:m1:revealed"


def test_twist_with_forbidden_concurrent():
    t = Twist(
        id="t1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=3,
        twist_type=TwistType.BETRAYAL,
        forbidden_concurrent_twists=("t2", "t3"),
    )
    assert t.forbidden_concurrent_twists == ("t2", "t3")
