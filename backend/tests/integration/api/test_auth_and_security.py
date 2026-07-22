"""API tests for authentication, RBAC, security headers, and error shape."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from nexguard.config.settings import Settings
from nexguard.interfaces.api.app import create_app

pytestmark = pytest.mark.integration


async def test_health_is_public_and_reports_status(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "stub"


async def test_security_headers_present(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers
    assert response.headers["X-Request-ID"]


async def test_unknown_route_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404


async def test_login_and_me_round_trip(
    client: httpx.AsyncClient,
    seeded: object,
    creds: SimpleNamespace,
    login: Callable[[str, str], Any],
    bearer: Callable[[str], dict[str, str]],
) -> None:
    token = await login(*creds.admin)
    me = await client.get("/api/v1/auth/me", headers=bearer(token))
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


async def test_wrong_password_is_401(
    client: httpx.AsyncClient, seeded: object, creds: SimpleNamespace
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": creds.admin[0], "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_protected_route_requires_auth(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/alerts")
    assert response.status_code == 401


async def test_viewer_cannot_generate_report(
    client: httpx.AsyncClient,
    seeded: object,
    creds: SimpleNamespace,
    login: Callable[[str, str], Any],
    bearer: Callable[[str], dict[str, str]],
) -> None:
    token = await login(*creds.viewer)
    alerts = (await client.get("/api/v1/alerts", headers=bearer(token))).json()
    assert alerts, "seed should have produced alerts"
    alert_id = alerts[0]["id"]
    response = await client.post(f"/api/v1/alerts/{alert_id}/report", headers=bearer(token))
    assert response.status_code == 403


async def test_auth_endpoint_rate_limited(
    make_settings: Callable[..., Settings],
) -> None:
    app = create_app(make_settings(auth_rate_limit_per_minute=3))
    container = app.state.container
    await container.startup()
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http:
            statuses = [
                (
                    await http.post(
                        "/api/v1/auth/login",
                        json={"email": "x@y.z", "password": "nope"},
                    )
                ).status_code
                for _ in range(5)
            ]
        assert 429 in statuses
    finally:
        await container.shutdown()
