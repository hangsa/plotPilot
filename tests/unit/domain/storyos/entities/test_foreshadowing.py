import pytest
from domain.storyos.contracts import AssetStatus
from domain.novel.value_objects.foreshadowing import ImportanceLevel
from domain.storyos.entities.foreshadowing import Foreshadowing


def test_foreshadowing_minimum_required():
    f = Foreshadowing(
        id="fs1", novel_id="n1", description="the scar on his hand",
        importance=ImportanceLevel.HIGH, status=AssetStatus.PLANTED,
        planted_in_chapter=2,
    )
    assert f.suggested_resolve_chapter is None
    assert f.resolved_in_chapter is None
    assert f.novel_id == "n1"


def test_foreshadowing_status_uses_asset_status():
    f = Foreshadowing(
        id="fs1", novel_id="n1", description="x",
        importance=ImportanceLevel.MEDIUM, status=AssetStatus.PLANTED,
        planted_in_chapter=1,
    )
    # REVEALED 是 spec 附录 C 映射的 resolved 状态
    f2 = f.resolve(chapter=10)
    assert f2.status == AssetStatus.REVEALED
    assert f2.resolved_in_chapter == 10


def test_foreshadowing_abandon():
    f = Foreshadowing(
        id="fs1", novel_id="n1", description="x",
        importance=ImportanceLevel.LOW, status=AssetStatus.PLANTED,
        planted_in_chapter=1,
    )
    f2 = f.abandon(chapter=20)
    assert f2.status == AssetStatus.DEAD


def test_foreshadowing_resolve_already_resolved_raises():
    f = Foreshadowing(
        id="fs1", novel_id="n1", description="x",
        importance=ImportanceLevel.MEDIUM, status=AssetStatus.REVEALED,
        planted_in_chapter=1, resolved_in_chapter=5,
    )
    with pytest.raises(ValueError, match="Cannot resolve"):
        f.resolve(chapter=10)


def test_foreshadowing_importance_validation():
    with pytest.raises(ValueError, match="importance"):
        Foreshadowing(
            id="fs1", novel_id="n1", description="x",
            importance=999,  # type: ignore[arg-type]
            status=AssetStatus.PLANTED, planted_in_chapter=1,
        )
