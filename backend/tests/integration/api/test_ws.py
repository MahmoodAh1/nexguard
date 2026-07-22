"""WebSocket live-streaming test using Starlette's TestClient."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nexguard.config.settings import Settings
from nexguard.interfaces.api.app import create_app
from nexguard.interfaces.api.container import Container
from nexguard.interfaces.bootstrap import seed_demo

pytestmark = [pytest.mark.integration, pytest.mark.slow]


async def _seed(settings: Settings, log: str, labels: str) -> None:
    container = Container(settings)
    await container.startup()
    try:
        await seed_demo(container, log_path=log, label_path=labels)
    finally:
        await container.shutdown()


def test_websocket_streams_alert_created(
    make_settings: Callable[..., Settings],
    creds: SimpleNamespace,
    hdfs_paths: tuple[str, str],
) -> None:
    settings = make_settings()
    asyncio.run(_seed(settings, *hdfs_paths))

    app = create_app(settings)
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": creds.analyst[0], "password": creds.analyst[1]},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        session_id = client.get("/api/v1/alerts", headers=headers).json()[0]["session_id"]

        with client.websocket_connect(f"/ws/alerts?token={token}") as ws:
            assert ws.receive_json()["topic"] == "connection.ready"
            # Re-scoring the session publishes an AlertCreated onto the bus.
            client.post(f"/api/v1/detection/sessions/{session_id}/run", headers=headers)
            message = ws.receive_json()
            assert message["topic"] == "alert.created"
            assert message["severity"] in {"medium", "high", "critical"}


def test_websocket_rejects_bad_token(make_settings: Callable[..., Settings]) -> None:
    app = create_app(make_settings())
    with (
        TestClient(app) as client,
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws/alerts?token=not-a-real-token") as ws,
    ):
        ws.receive_json()
