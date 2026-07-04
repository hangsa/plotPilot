import pytest
from application.storyos.services.twist_registry_service import TwistRegistryService
from application.storyos.services.promise_registry_service import PromiseRegistryService
from application.storyos.services.reveal_registry_service import RevealRegistryService
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.twist import Twist, TwistType
from domain.storyos.entities.promise import Promise
from domain.storyos.entities.reveal import Reveal


def test_twist_registry_create():
    svc = TwistRegistryService()
    t = Twist(id="t1", novel_id="n1", description="x",
              status=AssetStatus.ACTIVE, created_chapter=1,
              twist_type=TwistType.IDENTITY_REVEAL)
    svc.create(t)
    assert svc.get("t1") == t


def test_twist_registry_check_no_concurrent_twists():
    """Twist 互斥：forbidden_concurrent_twists 不允许同时 ACTIVE。"""
    svc = TwistRegistryService()
    t1 = Twist(id="t1", novel_id="n1", description="x",
               status=AssetStatus.ACTIVE, created_chapter=1,
               twist_type=TwistType.BETRAYAL,
               forbidden_concurrent_twists=("t2",))
    t2 = Twist(id="t2", novel_id="n1", description="y",
               status=AssetStatus.ACTIVE, created_chapter=2,
               twist_type=TwistType.TRUTH_REVEALED)
    svc.create(t1)
    svc.create(t2)
    # t1 被激活时检查 t2 不应同时 active
    with pytest.raises(ValueError, match="concurrent"):
        svc.activate_with_mutex_check("t1")


def test_promise_registry_fulfill():
    svc = PromiseRegistryService()
    p = Promise(id="p1", novel_id="n1", description="x",
                made_in_chapter=1, status=AssetStatus.ACTIVE, importance=80)
    svc.create(p)
    p2 = svc.fulfill("p1", chapter=10)
    assert p2.status == AssetStatus.FULFILLED
    assert svc.get("p1").status == AssetStatus.FULFILLED


def test_reveal_registry_reveal():
    svc = RevealRegistryService()
    r = Reveal(id="rv1", novel_id="n1", content="x",
               status=AssetStatus.HIDDEN, related_mystery="m1")
    svc.create(r)
    r2 = svc.reveal("rv1", chapter=15)
    assert r2.status == AssetStatus.REVEALED
    assert r2.revealed_in_chapter == 15
