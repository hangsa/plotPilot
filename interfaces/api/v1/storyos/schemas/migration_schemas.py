"""Migration 端点专用 DTO（1D 桩支持：preview/execute/status）。"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from domain.storyos.value_objects.format_error import FormatError


class MigrationPreviewResponse(BaseModel):
    """POST /migration/preview 响应（spec §4.5 锁定 5 元组）。"""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    scanned: int = Field(ge=0)
    migratable: int = Field(ge=0)
    skipped: int = Field(ge=0)
    invalid: int = Field(ge=0)
    sample_errors: list[FormatError] = Field(default_factory=list)


class MigrationExecuteRequest(BaseModel):
    """POST /migration/execute body。"""

    model_config = ConfigDict(extra="forbid")

    batch_size: int = Field(default=500, ge=1, le=5000)
    dry_run: bool = False


class MigrationExecuteResponse(BaseModel):
    """POST /migration/execute 响应。"""

    model_config = ConfigDict(extra="forbid")

    migration_id: str = Field(min_length=1, max_length=64)
    status: str = Field(min_length=1, max_length=32)
    batches_total: int = Field(ge=0)
    batches_done: int = Field(ge=0)
    errors: list[FormatError] = Field(default_factory=list)


class MigrationStatusResponse(BaseModel):
    """GET /migration/status/{migration_id} 响应。"""

    model_config = ConfigDict(extra="forbid")

    migration_id: str = Field(min_length=1, max_length=64)
    status: str = Field(min_length=1, max_length=32)
    progress_pct: float = Field(ge=0.0, le=100.0)
    eta_seconds: Optional[int] = Field(default=None, ge=0)
