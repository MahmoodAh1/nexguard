"""HTTP middleware: correlation IDs, security headers, and rate limiting."""

from __future__ import annotations

import time
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}
# A strict API CSP; relaxed on docs so Swagger UI can load its assets.
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Binds a request-scoped id to the log context and echoes it back."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if not request.url.path.startswith(_DOCS_PATHS):
            response.headers.setdefault("Content-Security-Policy", _API_CSP)
        return response


class _FixedWindowLimiter:
    """A per-key fixed-window rate limiter (in-memory)."""

    def __init__(self, limit_per_minute: int) -> None:
        self._limit = limit_per_minute
        self._window = 60.0
        self._state: dict[str, tuple[float, int]] = {}

    def check(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        window_start, count = self._state.get(key, (now, 0))
        if now - window_start >= self._window:
            window_start, count = now, 0
        if count >= self._limit:
            retry_after = int(self._window - (now - window_start)) + 1
            return False, retry_after
        self._state[key] = (window_start, count + 1)
        return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-client-IP rate limiting, with a stricter budget for auth endpoints."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        general_per_minute: int,
        auth_per_minute: int,
        auth_prefix: str = "/api/v1/auth",
        exempt_prefixes: tuple[str, ...] = ("/health", "/metrics/prometheus"),
    ) -> None:
        super().__init__(app)
        self._general = _FixedWindowLimiter(general_per_minute)
        self._auth = _FixedWindowLimiter(auth_per_minute)
        self._auth_prefix = auth_prefix
        self._exempt = exempt_prefixes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if path.startswith(self._exempt):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        is_auth = path.startswith(self._auth_prefix)
        limiter = self._auth if is_auth else self._general
        allowed, retry_after = limiter.check(f"{client_ip}:{'auth' if is_auth else 'general'}")
        if not allowed:
            return JSONResponse(
                status_code=429,
                media_type="application/problem+json",
                headers={"Retry-After": str(retry_after)},
                content={
                    "type": "about:blank",
                    "title": "Too Many Requests",
                    "status": 429,
                    "detail": "rate limit exceeded",
                },
            )
        return await call_next(request)


def register_middleware(app: FastAPI, *, general_per_minute: int, auth_per_minute: int) -> None:
    # Added outermost-first: correlation id wraps everything.
    app.add_middleware(
        RateLimitMiddleware,
        general_per_minute=general_per_minute,
        auth_per_minute=auth_per_minute,
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
