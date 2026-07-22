"""WebSocket endpoint streaming live domain events to the dashboard.

Authentication uses a short-lived access token passed as a query parameter,
since browsers cannot set Authorization headers on a WebSocket handshake. Two
tasks run concurrently — one forwarding bus events, one draining the socket to
detect disconnects — so the bus subscription is always released cleanly.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import cast

import psutil
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from nexguard.domain.errors import AuthenticationError
from nexguard.interfaces.api.container import Container

router = APIRouter(tags=["realtime"])

_WS_AUTH_FAILED = 4401
_METRICS_INTERVAL_SECONDS = 2.0


def _authenticate(container: Container, token: str) -> str | None:
    try:
        claims = container.tokens.decode(token)
        if claims.token_type != "access":
            raise AuthenticationError("access token required")
    except AuthenticationError:
        return None
    return claims.role


@router.websocket("/ws/alerts")
async def alerts_stream(websocket: WebSocket, token: str = Query(...)) -> None:
    container: Container = websocket.app.state.container
    role = _authenticate(container, token)
    if role is None:
        await websocket.close(code=_WS_AUTH_FAILED)
        return

    await websocket.accept()
    await websocket.send_json({"topic": "connection.ready", "role": role})

    subscription = cast(
        "AsyncGenerator[dict[str, object], None]", container.event_bus.subscribe("*")
    )
    forward = asyncio.create_task(_forward(websocket, subscription))
    drain = asyncio.create_task(_drain(websocket))
    try:
        await asyncio.wait({forward, drain}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        # Cancel and *await* the tasks before closing the subscription, so the
        # forwarding generator is no longer mid-iteration when we aclose it.
        for task in (forward, drain):
            task.cancel()
        for task in (forward, drain):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        with contextlib.suppress(RuntimeError):
            await subscription.aclose()


async def _forward(
    websocket: WebSocket, subscription: AsyncGenerator[dict[str, object], None]
) -> None:
    async for payload in subscription:
        await websocket.send_json(payload)


async def _drain(websocket: WebSocket) -> None:
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return


@router.websocket("/ws/metrics")
async def metrics_stream(websocket: WebSocket, token: str = Query(...)) -> None:
    container: Container = websocket.app.state.container
    if _authenticate(container, token) is None:
        await websocket.close(code=_WS_AUTH_FAILED)
        return

    await websocket.accept()
    push = asyncio.create_task(_push_metrics(websocket, container))
    drain = asyncio.create_task(_drain(websocket))
    try:
        await asyncio.wait({push, drain}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (push, drain):
            task.cancel()
        for task in (push, drain):
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task


async def _push_metrics(websocket: WebSocket, container: Container) -> None:
    process = psutil.Process()
    while True:
        async with container.database.session() as session:
            active_alerts = await container.alerts(session).total()
        virtual_memory = psutil.virtual_memory()
        await websocket.send_json(
            {
                "topic": "metrics.tick",
                "occurred_at": datetime.now(tz=UTC).isoformat(),
                "cpu_percent": psutil.cpu_percent(interval=None),
                "memory_percent": virtual_memory.percent,
                "process_rss_mb": round(process.memory_info().rss / 1e6, 1),
                "active_alerts": active_alerts,
            }
        )
        await asyncio.sleep(_METRICS_INTERVAL_SECONDS)
