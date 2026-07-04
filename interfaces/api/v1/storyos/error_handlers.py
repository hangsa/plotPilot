"""StoryOS error handlers: normalize RequestValidationError + Exception into ErrorResponse envelope."""
from __future__ import annotations

import traceback
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from interfaces.api.v1.storyos.schemas.common_schemas import (
    ErrorDetail,
    ErrorResponse,
)


def _detail_to_error_detail(detail: Any) -> ErrorDetail | None:
    """Reuse dict-shaped detail payloads from HTTPException as ErrorDetail."""
    if isinstance(detail, dict):
        code = detail.get("code")
        message = detail.get("message")
        sub_details = detail.get("details")
        if isinstance(code, str) and isinstance(message, str):
            return ErrorDetail(
                code=code,
                message=message,
                details=sub_details if isinstance(sub_details, dict) else None,
            )
    return None


def register_error_handlers(app: FastAPI) -> None:
    """Attach StoryOS error envelope handlers to the FastAPI app."""

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        field_errors: list[dict] = []
        for err in exc.errors():
            field_errors.append(
                {
                    "field": ".".join(str(loc) for loc in err.get("loc", ())),
                    "message": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
            )
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message="Request validation failed",
                    details={"errors": field_errors},
                )
            ).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        envelope = _detail_to_error_detail(exc.detail)
        if envelope is not None:
            return JSONResponse(
                status_code=exc.status_code,
                content=ErrorResponse(error=envelope).model_dump(),
            )
        message = str(exc.detail) if exc.detail is not None else "HTTP error"
        body = ErrorResponse(
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=message,
            )
        ).model_dump()
        # Preserve legacy top-level ``detail`` for non-StoryOS HTTPExceptions
        # (e.g. scene-director 500 path) so existing clients keep reading.
        body["detail"] = message
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
        )

    @app.exception_handler(Exception)
    async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred",
                )
            ).model_dump(),
        )