from __future__ import annotations

import structlog
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger("gateway.errors")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all exception handler to ensure structured logging and consistent JSON responses.
    Reduces code duplication in routes by handling common error scenarios globally.
    """
    if isinstance(exc, StarletteHTTPException):
        status_code = exc.status_code
        detail = exc.detail
        headers = getattr(exc, "headers", None)
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        detail = "Internal Server Error"
        headers = None
        # Log full error details for 500s
        logger.error(
            "unhandled_exception",
            error=str(exc),
            path=request.url.path,
            method=request.method,
            user_id=getattr(request.state, "user", None).user_id
            if hasattr(request.state, "user") and request.state.user
            else "anonymous",
        )

    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "status": "error"},
        headers=headers,
    )
