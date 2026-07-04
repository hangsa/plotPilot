"""StoryOS subpackage shared DTOs: pagination + error envelope."""
from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=200)
    total_pages: int = Field(ge=0)
    has_next: bool
    has_prev: bool

    @model_validator(mode="before")
    @classmethod
    def _auto_compute(cls, data: Any) -> Any:
        """Auto-fill derived pagination fields when caller omits them."""
        if isinstance(data, dict) and "total_pages" not in data:
            total = data.get("total", 0)
            page = data.get("page", 1)
            page_size = data.get("page_size", 1)
            total_pages = (total + page_size - 1) // page_size if total > 0 else 0
            data["total_pages"] = total_pages
            data.setdefault("has_next", page < total_pages)
            data.setdefault("has_prev", page > 1)
        return data

    @classmethod
    def compute(cls, total: int, page: int, page_size: int) -> "PaginationMeta":
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return cls(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class ListResponseEnvelope(BaseModel, Generic[T]):
    """List endpoint unified envelope."""

    model_config = ConfigDict(extra="forbid")

    data: list[T]
    meta: PaginationMeta


class ErrorDetail(BaseModel):
    """Error response detail."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=2000)
    details: Optional[dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response envelope."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail