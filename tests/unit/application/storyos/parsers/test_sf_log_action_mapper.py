from application.storyos.parsers.sf_log_action_mapper import SFLogActionMapper
from domain.evolution.contracts import ActionType
from domain.storyos.contracts import SFLogType
from domain.storyos.value_objects.sf_log import SFLogRecord


def _rec(log_type, params, asset_id=None):
    return SFLogRecord(
        log_type=log_type, params=params, raw="<!-- ... -->",
        chapter_id=1, char_position=0, asset_id=asset_id,
    )


def test_mapper_emits_action_for_location_change():
    """spec §3.3 锁定：CHARACTER_LOCATION_CHANGE → MOVE_CHARACTER。"""
    m = SFLogActionMapper()
    rec = _rec(
        SFLogType.CHARACTER_LOCATION_CHANGE,
        {"char_id": "alice", "location": "cave"},
        asset_id="alice",
    )
    actions, skipped = m.map_records([rec])
    assert len(actions) == 1
    assert actions[0].type == ActionType.MOVE_CHARACTER.value
    assert skipped == set()


def test_mapper_skips_mystery_clue():
    """spec §3.3 锁定：MYSTERY_CLUE 是 NOT_MAPPED（只写 StoryOS，不进 Evolution）。"""
    m = SFLogActionMapper()
    rec = _rec(
        SFLogType.MYSTERY_CLUE,
        {"mystery_id": "m1", "content": "blood"},
        asset_id="m1",
    )
    actions, skipped = m.map_records([rec])
    assert actions == []
    assert SFLogType.MYSTERY_CLUE in skipped


def test_mapper_maps_exactly_6_types():
    """spec §3.3 锁定 6 映射 + 5 跳过。"""
    m = SFLogActionMapper()
    # spec 锁定的 6 映射
    expected_mapped = {
        SFLogType.CHARACTER_LOCATION_CHANGE,
        SFLogType.CHARACTER_PHYSICAL_CHANGE,
        SFLogType.CHARACTER_RELATION_CHANGE,
        SFLogType.KNOWLEDGE_GAIN,
        SFLogType.CONFLICT_ESCALATE,
        SFLogType.GOAL_MILESTONE,
    }
    # spec 锁定的 5 NOT_MAPPED
    expected_skipped = {
        SFLogType.CHARACTER_EMOTION,
        SFLogType.MYSTERY_CLUE,
        SFLogType.TWIST_REVEAL,
        SFLogType.EXPECTATION_FULFILL,
        SFLogType.REGISTRY_CREATE,
    }
    # 跑全 11 类验证
    mapped_seen: set[SFLogType] = set()
    skipped_seen: set[SFLogType] = set()
    for log_type in SFLogType:
        rec = _rec(log_type, {"k": "v"}, asset_id="x")
        actions, skipped = m.map_records([rec])
        if actions:
            mapped_seen.add(log_type)
        else:
            skipped_seen.update(skipped)
    assert mapped_seen == expected_mapped
    assert skipped_seen == expected_skipped
    assert len(mapped_seen) == 6
    assert len(skipped_seen) == 5
