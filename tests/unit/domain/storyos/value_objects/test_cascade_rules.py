from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep, CascadeResult, CascadeRules


def _step(src_type: str, src_id: str, dst_type: str, dst_id: str):
    return CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type=src_type,
        source_asset_id=src_id,
        target_asset_type=dst_type,
        target_asset_id=dst_id,
        new_status=AssetStatus.ACTIVE,
    )


def test_cascade_result_empty():
    r = CascadeResult()
    assert r.steps_executed == []
    assert r.blocked_steps == []
    assert r.max_depth_reached == 0


def test_cascade_rules_apply_to_no_cycle():
    rules = CascadeRules()
    s1 = _step("mystery", "m1", "expectation", "e1")
    s2 = _step("expectation", "e1", "promise", "p1")
    visited: set[str] = set()
    r1 = rules.apply_to(s1, visited, max_depth=3)
    assert r1["would_create_cycle"] is False
    assert "m1" in visited
    r2 = rules.apply_to(s2, visited, max_depth=3)
    assert r2["would_create_cycle"] is False
    assert "e1" in visited


def test_cascade_rules_detects_cycle():
    rules = CascadeRules()
    visited: set[str] = {"e1", "p1", "m1"}
    s = _step("promise", "p1", "expectation", "e1")
    r = rules.apply_to(s, visited, max_depth=3)
    assert r["would_create_cycle"] is True


def test_cascade_rules_max_depth():
    rules = CascadeRules()
    visited: set[str] = set()
    s = _step("mystery", "m1", "expectation", "e1")
    r = rules.apply_to(s, visited, max_depth=0)
    assert r["depth_exceeded"] is True
    assert r["would_create_cycle"] is False
