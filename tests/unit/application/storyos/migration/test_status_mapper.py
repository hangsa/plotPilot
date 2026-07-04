"""status_mapper 单元测试。

薄包装 1A ForeshadowingMapper.convert_old_status_to_new，添加：
- 异常类型定义（UnknownLegacyStatusError）
- 批量转换 API（map_many）
- 跳过计数（map_with_skip）
"""
from __future__ import annotations

import pytest

from application.storyos.migration.status_mapper import (
    StatusMapper,
    UnknownLegacyStatusError,
)
from domain.storyos.contracts import AssetStatus
from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingRecord,
)


def test_map_planted_to_PLANTED():
    """旧 planted → 新 PLANTED（identity）。"""
    assert StatusMapper.map_status("planted") == AssetStatus.PLANTED


def test_map_resolved_to_REVEALED():
    """旧 resolved → 新 REVEALED（⚡ 重新映射，spec 附录 C 锁定）。"""
    assert StatusMapper.map_status("resolved") == AssetStatus.REVEALED


def test_map_abandoned_to_DEAD():
    """旧 abandoned → 新 DEAD（⚡ 重新映射）。"""
    assert StatusMapper.map_status("abandoned") == AssetStatus.DEAD


def test_map_unknown_raises():
    """未在映射表的旧值抛 UnknownLegacyStatusError。"""
    with pytest.raises(UnknownLegacyStatusError) as exc_info:
        StatusMapper.map_status("weird_state")
    assert "weird_state" in str(exc_info.value)


def test_map_status_or_skip_returns_none_for_unknown():
    """map_status_or_skip 返回 None（不抛异常）—— 用于降级到 invalid 计数。"""
    assert StatusMapper.map_status_or_skip("planted") == AssetStatus.PLANTED
    assert StatusMapper.map_status_or_skip("weird_state") is None


def test_map_many_returns_pairs():
    """map_many 批量转换，返回 (new_status, record) 元组列表。"""
    records = [
        LegacyForeshadowingRecord(
            id="fs-1", novel_id="n1", description="d",
            planted_chapter=1, due_chapter=None, resolved_chapter=None,
            status="planted", importance=2, subtext_type=None,
        ),
        LegacyForeshadowingRecord(
            id="fs-2", novel_id="n1", description="d",
            planted_chapter=1, due_chapter=None, resolved_chapter=5,
            status="resolved", importance=2, subtext_type=None,
        ),
    ]
    pairs = StatusMapper.map_many(records)
    assert len(pairs) == 2
    assert pairs[0][0] == AssetStatus.PLANTED
    assert pairs[1][0] == AssetStatus.REVEALALED if False else pairs[1][0] == AssetStatus.REVEALED


def test_map_with_skip_partitions_known_unknown():
    """map_with_skip 把 records 拆分为 (migratable, invalid_ids)。"""
    records = [
        LegacyForeshadowingRecord(
            id="fs-1", novel_id="n1", description="d",
            planted_chapter=1, due_chapter=None, resolved_chapter=None,
            status="planted", importance=2, subtext_type=None,
        ),
        LegacyForeshadowingRecord(
            id="fs-bad", novel_id="n1", description="d",
            planted_chapter=1, due_chapter=None, resolved_chapter=None,
            status="legacy_weird", importance=2, subtext_type=None,
        ),
    ]
    migratable, invalid_ids = StatusMapper.map_with_skip(records)
    assert len(migratable) == 1
    assert migratable[0][0].id == "fs-1"
    assert migratable[0][1] == AssetStatus.PLANTED
    assert invalid_ids == ["fs-bad"]