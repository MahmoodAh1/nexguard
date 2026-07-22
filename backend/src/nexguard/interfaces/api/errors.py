"""Exception handlers: domain errors -> RFC-9457 problem+json responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from nexguard.domain.errors import (
    AuthenticationError,
    AuthorizationError,
    NexGuardError,
    NotFoundError,
    RateLimitError,
    ReportGenerationError,
    ValidationError,
)

_PROBLEM_JSON = "application/problem+json"


def _problem(
    status: int, title: str, detail: str, *, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type=_PROBLEM_JSON,
        headers=headers,
        content={
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": detail,
        },
    )


async def _not_found(_: Request, exc: Exception) -> JSONResponse:
    return _problem(404, "Not Found", str(exc))


async def _validation(_: Request, exc: Exception) -> JSONResponse:
    return _problem(400, "Bad Request", str(exc))


async def _authentication(_: Request, exc: Exception) -> JSONResponse:
    return _problem(401, "Unauthorized", str(exc), headers={"WWW-Authenticate": "Bearer"})


async def _authorization(_: Request, exc: Exception) -> JSONResponse:
    return _problem(403, "Forbidden", str(exc))


async def _rate_limit(_: Request, exc: Exception) -> JSONResponse:
    retry_after = exc.retry_after_seconds if isinstance(exc, RateLimitError) else 60
    return _problem(429, "Too Many Requests", str(exc), headers={"Retry-After": str(retry_after)})


async def _report_generation(_: Request, exc: Exception) -> JSONResponse:
    return _problem(502, "Bad Gateway", f"report generation failed: {exc}")


async def _generic(_: Request, exc: Exception) -> JSONResponse:
    return _problem(500, "Internal Server Error", str(exc))


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(NotFoundError, _not_found)
    app.add_exception_handler(ValidationError, _validation)
    app.add_exception_handler(AuthenticationError, _authentication)
    app.add_exception_handler(AuthorizationError, _authorization)
    app.add_exception_handler(RateLimitError, _rate_limit)
    app.add_exception_handler(ReportGenerationError, _report_generation)
    app.add_exception_handler(NexGuardError, _generic)
