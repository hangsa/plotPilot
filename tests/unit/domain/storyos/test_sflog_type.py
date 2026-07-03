from domain.storyos.contracts import SFLogType, RELATIONAL_LOG_TYPES


def test_sflog_type_has_11_members():
    assert len(SFLogType) == 11


def test_sflog_type_member_names():
    expected = {
        "CHARACTER_EMOTION", "CHARACTER_RELATION_CHANGE", "CHARACTER_LOCATION_CHANGE",
        "CHARACTER_PHYSICAL_CHANGE", "KNOWLEDGE_GAIN", "CONFLICT_ESCALATE",
        "MYSTERY_CLUE", "TWIST_REVEAL", "EXPECTATION_FULFILL",
        "GOAL_MILESTONE", "REGISTRY_CREATE",
    }
    assert {m.name for m in SFLogType} == expected


def test_sflog_type_values_are_snake_case():
    for m in SFLogType:
        assert m.value == m.name.lower().replace("_", "_")  # sanity


def test_relational_log_types_constant():
    assert isinstance(RELATIONAL_LOG_TYPES, frozenset)
    assert SFLogType.CHARACTER_RELATION_CHANGE in RELATIONAL_LOG_TYPES
    assert len(RELATIONAL_LOG_TYPES) == 1
    assert SFLogType.MYSTERY_CLUE not in RELATIONAL_LOG_TYPES
