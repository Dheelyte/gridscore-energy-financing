"""Consistent error envelope and exception handlers.

Every error response has the shape::

    {"error": {"code": "forbidden", "message": "...", "details": {...}}}

so clients (and the generated TypeScript client) can handle failures uniformly.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

log = get_logger("app.errors")


class APIError(Exception):
    """Base application error rendered into the standard envelope."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.headers = headers or {}


class AuthenticationError(APIError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"


class AuthorizationError(APIError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class NotFoundError(APIError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(APIError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class RateLimitError(APIError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class ServiceUnavailableError(APIError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "validation_error", "Request validation failed", {"errors": exc.errors()}
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope("http_error", str(exc.detail)),
            headers=getattr(exc, "headers", None) or {},
        )
