"""Foreshadowing mapper — entity ↔ ORM row.

The entity's `planted_in_chapter` is mapped to/from BaseRegistrySchema's
`created_chapter` column. `importance` (ImportanceLevel int-enum) is stored
as its `.name` string and reconstructed via `ImportanceLevel[name]`.

Also exposes `convert_old_status_to_new` (spec 附录 C) for the 1E migration
script that bridges the legacy ForeshadowingStatus (planted/resolved/abandoned)
to AssetStatus (PLANTED/REVEALED/DEAD).
"""
from __future__ import annotations

from domain.novel.value_objects.foreshadowing import ImportanceLevel
from domain.storyos.contracts import AssetStatus
from domain.storyos.entities.foreshadowing import Foreshadowing
from infrastructure.persistence.storyos.schemas.foreshadowing_schema import (
    ForeshadowingSchema,
)


class ForeshadowingMapper:
    # spec 附录 C 锁定：旧字符串状态 → 新 AssetStatus 映射
    _OLD_TO_NEW = {
        "planted": AssetStatus.PLANTED,
        "resolved": AssetStatus.REVEALED,
        "abandoned": AssetStatus.DEAD,
    }

    @staticmethod
    def convert_old_status_to_new(old: str) -> AssetStatus:
        """spec 附录 C 锁定旧→新 Foreshadowing 状态映射。"""
        if old not in ForeshadowingMapper._OLD_TO_NEW:
            raise ValueError(f"Unknown old foreshadowing status: {old!r}")
        return ForeshadowingMapper._OLD_TO_NEW[old]

    @staticmethod
    def to_orm(f: Foreshadowing) -> ForeshadowingSchema:
        return ForeshadowingSchema(
            id=f.id,
            project_id=f.novel_id,
            created_chapter=f.planted_in_chapter,
            status=f.status.value,
            description=f.description,
            linked_assets={},
            importance=f.importance.name,
            planted_in_chapter=f.planted_in_chapter,
            suggested_resolve_chapter=f.suggested_resolve_chapter,
            resolved_in_chapter=f.resolved_in_chapter,
        )

    @staticmethod
    def to_domain(row: ForeshadowingSchema) -> Foreshadowing:
        return Foreshadowing(
            id=row.id,
            novel_id=row.project_id,
            description=row.description,
            importance=ImportanceLevel[row.importance],
            status=AssetStatus(row.status),
            planted_in_chapter=row.created_chapter,
            suggested_resolve_chapter=row.suggested_resolve_chapter,
            resolved_in_chapter=row.resolved_in_chapter,
        )