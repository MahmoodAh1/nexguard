"""FastAPI application factory.

Wires the composition root into a FastAPI app: lifespan-managed container
startup/shutdown, middleware (correlation id, security headers, rate limiting,
CORS), RFC-9457 error handling, and all routers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from nexguard import __version__
from nexguard.config.settings import Settings, get_settings
from nexguard.interfaces.api.container import Container
from nexguard.interfaces.api.errors import register_exception_handlers
from nexguard.interfaces.api.middleware import register_middleware
from nexguard.interfaces.api.routers import (
    alerts,
    auth,
    detection,
    feedback,
    health,
    metrics,
    ws,
)
from nexguard.observability.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)
    container = Container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await container.startup()
        try:
            yield
        finally:
            await container.shutdown()

    app = FastAPI(
        title="NexGuard API",
        version=__version__,
        summary="AI-Powered Security Operations Platform",
        lifespan=lifespan,
    )
    app.state.container = container

    register_exception_handlers(app)
    register_middleware(
        app,
        general_per_minute=settings.rate_limit_per_minute,
        auth_per_minute=settings.auth_rate_limit_per_minute,
    )
    # CORS added last so it is outermost — even rate-limited responses carry it.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    for router in (
        health.router,
        metrics.scrape_router,
        auth.router,
        alerts.router,
        detection.router,
        feedback.router,
        metrics.router,
        ws.router,
    ):
        app.include_router(router)

    return app


app = create_app()
