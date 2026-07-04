"""status_mapper —— 旧→新 status 映射的薄包装。

直接复用 1A ForeshadowingMapper.convert_old_status_to_new，
添加批量 API + 降级返回 None 的版本（供 scan 报告 invalid 计数）。
"""
from __future__ import annotations

from typing import List, Tuple

from domain.storyos.contracts import AssetStatus
from infrastructure.persistence.storyos.mappers.foreshadowing_mapper import (
    ForeshadowingMapper,
)

from application.storyos.migration.legacy_foreshadowing_adapter import (
    LegacyForeshadowingRecord,
)


class UnknownLegacyStatusError(ValueError):
    """旧 status 值不在映射表内。"""


class StatusMapper:
    @staticmethod
    def map_status(old_status: str) -> AssetStatus:
        try:
            return ForeshadowingMapper.convert_old_status_to_new(old_status)
        except ValueError as e:
            raise UnknownLegacyStatusError(
                f"Unknown legacy foreshadowing status: {old_status!r}"
            ) from e

    @staticmethod
    def map_status_or_skip(old_status: str):
        """返回 AssetStatus 或 None（None 表示 invalid，跳过）。"""
        try:
            return ForeshadowingMapper.convert_old_status_to_new(old_status)
        except ValueError:
            return None

    @staticmethod
    def map_many(
        records: List[LegacyForeshadowingRecord],
    ) -> List[Tuple[AssetStatus, LegacyForeshadowingRecord]]:
        """批量映射；不存在的 status 抛 UnknownLegacyStatusError。

        返回 (new_status, record) 元组列表（status 在前以方便下游直接聚合）。
        """
        return [(StatusMapper.map_status(r.status), r) for r in records]

    @staticmethod
    def map_with_skip(
        records: List[LegacyForeshadowingRecord],
    ) -> Tuple[List[Tuple[LegacyForeshadowingRecord, AssetStatus]], List[str]]:
        """返回 (migratable_pairs, invalid_ids)。

        - migratable_pairs: (record, new_status) 元组列表
        - invalid_ids: 损坏 / 未知 status 的旧 ID 列表
        """
        migratable: List[Tuple[LegacyForeshadowingRecord, AssetStatus]] = []
        invalid_ids: List[str] = []
        for r in records:
            new_status = StatusMapper.map_status_or_skip(r.status)
            if new_status is None:
                invalid_ids.append(r.id)
            else:
                migratable.append((r, new_status))
        return migratable, invalid_ids