"""SFLog 端点：raw 文本查询 + reparse（C2 1D 桩）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Query

from interfaces.api.v1.storyos.dependencies import get_sflog_service
from interfaces.api.v1.storyos.schemas.sflog_schemas import (
    MatchReportDTO,
    SFLogRawResponse,
    SFLogReparseResponse,
)

router = APIRouter(prefix="/api/v1/storyos/{project_id}/sflog", tags=["storyos-sflog"])


@router.get("/raw", response_model=SFLogRawResponse)
async def sflog_raw(
    project_id: str = Path(..., min_length=1),
    chapter: int = Query(..., ge=1),
    _service=Depends(get_sflog_service),
) -> SFLogRawResponse:
    """1D stub: chapter-text fetch + parse wiring lands in 1E."""
    return SFLogRawResponse(
        chapter_id=chapter,
        raw_text="",
        records=[],
        sf_log_count=0,
    )


@router.post("/reparse/{chapter_id}", response_model=SFLogReparseResponse)
async def sflog_reparse(
    project_id: str = Path(..., min_length=1),
    chapter_id: int = Path(..., ge=1),
    _service=Depends(get_sflog_service),
) -> SFLogReparseResponse:
    """1D stub: parse + validate + match wiring lands in 1E."""
    return SFLogReparseResponse(
        chapter_id=chapter_id,
        parsed_count=0,
        format_errors=[],
        match_report=MatchReportDTO(
            predeclared_total=0,
            predeclared_implemented=0,
            missing_changes=[],
            unexpected_records=[],
            match_rate=0.0,
            should_retry=False,
            has_warnings=False,
        ),
    )