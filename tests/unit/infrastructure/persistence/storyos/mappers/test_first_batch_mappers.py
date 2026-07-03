from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.conflict import Conflict, ConflictIntensity
from domain.storyos.entities.mystery import Clue, Mystery
from domain.storyos.entities.twist import Twist, TwistType
from domain.storyos.entities.promise import Promise
from infrastructure.persistence.storyos.mappers.conflict_mapper import ConflictMapper
from infrastructure.persistence.storyos.mappers.mystery_mapper import MysteryMapper
from infrastructure.persistence.storyos.mappers.twist_mapper import TwistMapper
from infrastructure.persistence.storyos.mappers.promise_mapper import PromiseMapper


def test_conflict_round_trip():
    c = Conflict(
        id="c1", novel_id="n1", description="x",
        intensity=ConflictIntensity.MEDIUM, status=AssetStatus.ACTIVE,
        involved_characters=("a", "b"), created_chapter=1,
        linked_conflicts=("c2", "c3"),
    )
    row = ConflictMapper.to_orm(c)
    c2 = ConflictMapper.to_domain(row)
    assert c2 == c


def test_mystery_round_trip_with_clues():
    cl = Clue(id="cl1", mystery_id="m1", description="a",
              source_chapter=1, source_location="x")
    m = Mystery(
        id="m1", novel_id="n1", description="x",
        status=AssetStatus.PLANTED, created_chapter=1, clues=(cl,),
    )
    row = MysteryMapper.to_orm(m)
    m2 = MysteryMapper.to_domain(row)
    assert m2.clues == m.clues
    assert m2.id == m.id


def test_twist_round_trip():
    t = Twist(
        id="t1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1,
        twist_type=TwistType.IDENTITY_REVEAL,
        reveal_trigger="mystery:m1:revealed",
    )
    row = TwistMapper.to_orm(t)
    t2 = TwistMapper.to_domain(row)
    assert t2 == t


def test_promise_round_trip():
    p = Promise(
        id="p1", novel_id="n1", description="x",
        made_in_chapter=1, status=AssetStatus.ACTIVE, importance=80,
    )
    row = PromiseMapper.to_orm(p)
    p2 = PromiseMapper.to_domain(row)
    assert p2 == p


def test_promise_round_trip_fulfilled():
    # E1 review: explicitly exercise fulfilled_in_chapter so a silent-drop
    # bug in the ORM <-> mapper direction would be caught (entity default = None).
    p = Promise(
        id="p2", novel_id="n1", description="y",
        made_in_chapter=1, status=AssetStatus.FULFILLED, importance=90,
        fulfilled_in_chapter=5,
    )
    row = PromiseMapper.to_orm(p)
    p2 = PromiseMapper.to_domain(row)
    assert p2 == p
    assert p2.status == AssetStatus.FULFILLED
    assert p2.fulfilled_in_chapter == 5