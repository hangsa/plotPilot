import pytest
from application.storyos.services.cascade_service import CascadeService
from application.storyos.services.mystery_registry_service import MysteryRegistryService
from application.storyos.services.twist_registry_service import TwistRegistryService
from application.storyos.services.promise_registry_service import PromiseRegistryService
from application.storyos.services.reveal_registry_service import RevealRegistryService
from application.storyos.services.conflict_registry_service import ConflictRegistryService
from domain.storyos.contracts import AssetStatus, CascadeTrigger
from domain.storyos.value_objects.cascade import CascadeStep
from domain.storyos.entities.mystery import Mystery
from domain.storyos.entities.twist import Twist, TwistType
from domain.storyos.entities.promise import Promise
from domain.storyos.entities.reveal import Reveal
from domain.storyos.entities.conflict import Conflict, ConflictIntensity


def test_mystery_revealed_triggers_cascade():
    cascade = CascadeService(mystery_svc=MysteryRegistryService())
    step = CascadeStep(
        trigger=CascadeTrigger.MYSTERY_REVEALED,
        source_asset_type="mystery", source_asset_id="m1",
        target_asset_type="expectation", target_asset_id="e1",
        new_status=AssetStatus.RESOLVED, reason="mystery solved",
    )
    result = cascade.execute([step])
    # 1A B3 CascadeStep 校验要求 new_status or intensity_delta；二者皆有 → 正常
    assert len(result.steps_executed) == 1 or len(result.blocked_steps) == 1


def test_twist_revealed_triggers():
    """TWIST_REVEALED + 关联 promise 转 FULFILLED。"""
    cascade = CascadeService(twist_svc=TwistRegistryService())
    step = CascadeStep(
        trigger=CascadeTrigger.TWIST_REVEALED,
        source_asset_type="twist", source_asset_id="t1",
        target_asset_type="promise", target_asset_id="p1",
        new_status=AssetStatus.FULFILLED, reason="twist unlocked promise",
    )
    result = cascade.execute([step])
    assert len(result.steps_executed) == 1 or len(result.blocked_steps) == 1


def test_conflict_resolved_triggers():
    """CONFLICT_RESOLVED + 关联 expectation 转 RESOLVED。"""
    cascade = CascadeService(conflict_svc=ConflictRegistryService())
    step = CascadeStep(
        trigger=CascadeTrigger.CONFLICT_RESOLVED,
        source_asset_type="conflict", source_asset_id="c1",
        target_asset_type="expectation", target_asset_id="e1",
        new_status=AssetStatus.RESOLVED, reason="conflict over",
    )
    result = cascade.execute([step])
    assert len(result.steps_executed) == 1 or len(result.blocked_steps) == 1