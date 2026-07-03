import pytest
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.reveal import Reveal


def test_reveal_minimum_required():
    r = Reveal(
        id="rv1", novel_id="n1", content="x is the killer",
        status=AssetStatus.HIDDEN, related_mystery="m1",
    )
    assert r.revealed_in_chapter is None
    assert r.linked_to_conflict is None


def test_reveal_transition_hidden_to_revealed():
    r = Reveal(
        id="rv1", novel_id="n1", content="x",
        status=AssetStatus.HIDDEN, related_mystery="m1",
    )
    r2 = r.reveal(chapter=15)
    assert r2.status == AssetStatus.REVEALED
    assert r2.revealed_in_chapter == 15


def test_reveal_transition_already_revealed_raises():
    r = Reveal(
        id="rv1", novel_id="n1", content="x",
        status=AssetStatus.REVEALED, revealed_in_chapter=10,
        related_mystery="m1",
    )
    with pytest.raises(ValueError, match="Cannot reveal in status"):
        r.reveal(chapter=15)
