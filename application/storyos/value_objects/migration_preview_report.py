"""MigrationPreviewReport —— scan() 返回的 5 元组报告（与 1D DTO 对齐）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class MigrationSampleError:
    """样例错误（旧 ID + 错误代码 + 消息），最多保留前 10 条。"""
    old_id: str
    code: str
    message: str


@dataclass(frozen=True)
class MigrationPreviewReport:
    """迁移预览报告 5 元组（spec 附录 C + 1D MigrationPreviewResponse）。

    字段语义：
        total: 旧表记录总数
        scanned: 实际扫描的记录数
        migratable: 可迁移记录数（旧 status 在映射表 + 字段完整）
        skipped: 已迁移过（committed）的记录数（断点续跑命中）
        invalid: 损坏行（adapter_corrupted + unknown_status）
    """
    project_id: str
    total: int = 0
    scanned: int = 0
    migratable: int = 0
    skipped: int = 0
    invalid: int = 0
    sample_errors: List[MigrationSampleError] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "total": self.total,
            "scanned": self.scanned,
            "migratable": self.migratable,
            "skipped": self.skipped,
            "invalid": self.invalid,
            "sample_errors": [
                {"old_id": e.old_id, "code": e.code, "message": e.message}
                for e in self.sample_errors
            ],
        }