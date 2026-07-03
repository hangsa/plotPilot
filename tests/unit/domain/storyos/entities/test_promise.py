import pytest
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.promise import Promise


def test_promise_minimum_required():
    p = Promise(
        id="p1", novel_id="n1", description="alice will return",
        made_in_chapter=1, status=AssetStatus.ACTIVE, importance=80,
    )
    assert p.fulfilled_in_chapter is None
    assert p.importance == 80


def test_promise_fulfill_returns_new():
    p = Promise(
        id="p1", novel_id="n1", description="x",
        made_in_chapter=1, status=AssetStatus.ACTIVE, importance=50,
    )
    p2 = p.fulfill(chapter=10)
    assert p2 is not p
    assert p2.status == AssetStatus.FULFILLED
    assert p2.fulfilled_in_chapter == 10


def test_promise_fulfill_already_fulfilled_raises():
    p = Promise(
        id="p1", novel_id="n1", description="x",
        made_in_chapter=1, status=AssetStatus.FULFILLED,
        fulfilled_in_chapter=5, importance=50,
    )
    with pytest.raises(ValueError, match="Cannot fulfill promise in status"):
        p.fulfill(chapter=10)


def test_promise_importance_out_of_range():
    with pytest.raises(ValueError, match="importance"):
        Promise(
            id="p1", novel_id="n1", description="x",
            made_in_chapter=1, status=AssetStatus.ACTIVE, importance=150,
        )
    with pytest.raises(ValueError, match="importance"):
        Promise(
            id="p1", novel_id="n1", description="x",
            made_in_chapter=1, status=AssetStatus.ACTIVE, importance=-1,
        )