import pytest
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.expectation import Expectation


def test_expectation_minimum_required():
    e = Expectation(
        id="e1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1, intensity=50,
    )
    assert e.intensity == 50


def test_expectation_intensify_clamps_upper():
    e = Expectation(
        id="e1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1, intensity=95,
    )
    e2 = e.intensify(30)
    assert e2.intensity == 100  # clamped


def test_expectation_intensify_clamps_lower():
    e = Expectation(
        id="e1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1, intensity=10,
    )
    e2 = e.intensify(-50)
    assert e2.intensity == 0


def test_expectation_intensify_normal():
    e = Expectation(
        id="e1", novel_id="n1", description="x",
        status=AssetStatus.ACTIVE, created_chapter=1, intensity=50,
    )
    e2 = e.intensify(20)
    assert e2.intensity == 70


def test_expectation_initial_intensity_validated():
    with pytest.raises(ValueError):
        Expectation(
            id="e1", novel_id="n1", description="x",
            status=AssetStatus.ACTIVE, created_chapter=1, intensity=150,
        )