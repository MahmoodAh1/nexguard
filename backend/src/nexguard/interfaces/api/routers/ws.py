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
from typing import cast

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from nexguard.domain.errors import AuthenticationError
from nexguard.interfaces.api.container import Container

router = APIRouter(tags=["realtime"])

_WS_AUTH_FAILED = 4401


@router.websocket("/ws/alerts")
async def alerts_stream(websocket: WebSocket, token: str = Query(...)) -> None:
    container: Container = websocket.app.state.container
    try:
        claims = container.tokens.decode(token)
        if claims.token_type != "access":
            raise AuthenticationError("access token required")
    except AuthenticationError:
        await websocket.close(code=_WS_AUTH_FAILED)
        return

    await websocket.accept()
    await websocket.send_json({"topic": "connection.ready", "role": claims.role})

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
