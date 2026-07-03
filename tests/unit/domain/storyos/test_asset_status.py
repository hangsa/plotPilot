import re
from domain.storyos.contracts import AssetStatus


def test_asset_status_has_12_members():
    assert len(AssetStatus) == 12


def test_asset_status_member_values():
    expected = {
        "ACTIVE", "ACCUMULATING", "PLANTED", "DEVELOPING",
        "HIDDEN", "READY_TO_FULFILL", "ESCALATED", "REVEALED",
        "FULFILLED", "RESOLVED", "ABANDONED", "DEAD",
    }
    actual = {m.name for m in AssetStatus}
    assert actual == expected


def test_asset_status_values_are_snake_case_strings():
    pattern = re.compile(r"^[a-z_]+$")
    for m in AssetStatus:
        assert pattern.match(m.value), f"{m.name}={m.value!r} not snake_case"


def test_asset_status_is_string_enum():
    assert isinstance(AssetStatus.ACTIVE, str)
    assert AssetStatus.ACTIVE == "active"
    assert AssetStatus.ACTIVE.value == "active"