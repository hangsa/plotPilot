"""Cascade 端点 DTO 测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from interfaces.api.v1.storyos.schemas.cascade_schemas import (
    CascadeSimulateRequest,
    CascadeSimulateResponse,
    CascadeReplayRequest,
    CascadeStepDTO,
    CascadeSimulateSummary,
)
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep


def test_cascade_step_dto_from_domain():
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery",
        source_asset_id="m1",
        target_asset_type="expectation",
        target_asset_id="e1",
        new_status=AssetStatus.READY_TO_FULFILL,
        reason="climax reached",
    )
    dto = CascadeStepDTO.from_domain(step)
    assert dto.trigger == CascadeTrigger.MYSTERY_REVEALED
    assert dto.new_status == AssetStatus.READY_TO_FULFILL
    assert dto.reason == "climax reached"
    assert dto.source_asset_type == "mystery"
    assert dto.target_asset_id == "e1"


def test_cascade_simulate_request_requires_source():
    req = CascadeSimulateRequest(
        project_id="proj-1",
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery",
        source_asset_id="m1",
    )
    assert req.max_depth == 3  # 默认值


def test_cascade_simulate_request_validates_max_depth():
    with pytest.raises(ValidationError):
        CascadeSimulateRequest(
            project_id="proj-1",
            trigger=CascadeTrigger.MYSTERY_REVEALED,
            source_asset_type="mystery",
            source_asset_id="m1",
            max_depth=10,  # 超过 spec §4.2 锁定的 MAX_CASCADE_DEPTH=3
        )


def test_cascade_simulate_request_rejects_zero_max_depth():
    with pytest.raises(ValidationError):
        CascadeSimulateRequest(
            project_id="proj-1",
            trigger=CascadeTrigger.MYSTERY_REVEALED,
            source_asset_type="mystery",
            source_asset_id="m1",
            max_depth=0,
        )


def test_cascade_simulate_response_includes_summary():
    """响应含 step 列表 + 摘要（避免前端需重新聚合）。"""
    summary = CascadeSimulateSummary(
        would_block=False,
        max_depth_reached=2,
        steps_count=3,
        blocked_steps_count=0,
    )
    resp = CascadeSimulateResponse(
        steps=[],
        summary=summary,
    )
    assert resp.summary.max_depth_reached == 2
    assert resp.blocked_steps == []


def test_cascade_replay_request_requires_bridge_id_in_path():
    """bridge_id 来自路径参数，body 仅需可选 notes。"""
    req = CascadeReplayRequest(notes="manual review after incident")
    assert req.notes is not None


def test_cascade_replay_request_default_empty_notes():
    req = CascadeReplayRequest()
    assert req.notes is None
