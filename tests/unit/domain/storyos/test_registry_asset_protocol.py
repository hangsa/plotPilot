"""Tests for the runtime-checkable RegistryAsset Protocol.

The Protocol is the duck-typing contract every narrative asset entity
will satisfy in Group C.
"""
from domain.storyos.contracts import RegistryAsset, AssetStatus


def test_empty_class_does_not_satisfy_protocol():
    class Empty:
        pass
    assert not isinstance(Empty(), RegistryAsset)


def test_partial_class_does_not_satisfy_protocol():
    class Partial:
        id = "x"
        status = AssetStatus.ACTIVE
        # missing linked_assets
    assert not isinstance(Partial(), RegistryAsset)


def test_full_class_satisfies_protocol():
    class Full:
        id = "x"
        status = AssetStatus.ACTIVE
        linked_assets: dict = {}
    assert isinstance(Full(), RegistryAsset)