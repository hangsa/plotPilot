"""CascadeStep（spec §3.2 单步级联动作）。"""
import pytest
from pydantic import ValidationError
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep


def test_cascade_step_minimum_required():
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery",
        source_asset_id="m1",
        target_asset_type="expectation",
        target_asset_id="e1",
        new_status=AssetStatus.ACTIVE,
        reason="climax",
    )
    assert step.trigger == CascadeTrigger.MYSTERY_REVEALED
    assert step.reason == "climax"
    assert step.intensity_delta is None


def test_cascade_step_with_intensity_delta():
    step = CascadeStep(
        trigger=CascadeTrigger.CONFLICT_ESCALATED,
        source_asset_type="conflict",
        source_asset_id="c1",
        target_asset_type="expectation",
        target_asset_id="e1",
        intensity_delta=30,
        reason="escalated to CRITICAL",
    )
    assert step.intensity_delta == 30
    assert step.new_status is None


def test_cascade_step_requires_status_or_intensity():
    with pytest.raises(ValidationError, match="new_status or intensity_delta"):
        CascadeStep(
            trigger=CascadeTrigger.MYSTERY_REVEALED,
            source_asset_type="mystery",
            source_asset_id="m1",
            target_asset_type="expectation",
            target_asset_id="e1",
            reason="bad",
        )


def test_cascade_step_default_reason_is_empty():
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery",
        source_asset_id="m1",
        target_asset_type="expectation",
        target_asset_id="e1",
        new_status=AssetStatus.ACTIVE,
    )
    assert step.reason == ""


def test_cascade_step_is_frozen():
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery",
        source_asset_id="m1",
        target_asset_type="expectation",
        target_asset_id="e1",
        new_status=AssetStatus.ACTIVE,
    )
    with pytest.raises(ValidationError):
        step.reason = "x"  # type: ignore[misc]
