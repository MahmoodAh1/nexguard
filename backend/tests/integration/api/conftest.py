"""Fixtures for API integration tests (full app over a temp SQLite DB).

Shared helpers are exposed as fixtures (not importable module functions) so test
modules never need to import from conftest — which pytest's default import mode
does not support without package boilerplate.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from nexguard.config.settings import Settings
from nexguard.interfaces.api.app import create_app
from nexguard.interfaces.api.container import Container
from nexguard.interfaces.bootstrap import seed_demo

_FIXTURES = Path(__file__).parents[2] / "fixtures" / "hdfs"
HDFS_LOG = str(_FIXTURES / "hdfs_sample.log")
HDFS_LABELS = str(_FIXTURES / "anomaly_label.csv")

# Demo credentials created by seed_demo.
_ADMIN = ("admin@nexguard.local", "NexGuardAdmin!23")
_ANALYST = ("analyst@nexguard.local", "NexGuardAnalyst!23")
_VIEWER = ("viewer@nexguard.local", "NexGuardViewer!23")


@pytest.fixture
def creds() -> SimpleNamespace:
    return SimpleNamespace(admin=_ADMIN, analyst=_ANALYST, viewer=_VIEWER)


@pytest.fixture
def hdfs_paths() -> tuple[str, str]:
    return HDFS_LOG, HDFS_LABELS


@pytest.fixture
def make_settings(tmp_path: Path) -> Callable[..., Settings]:
    def factory(**overrides: object) -> Settings:
        base: dict[str, Any] = {
            "database_url": f"sqlite+aiosqlite:///{(tmp_path / 'api.db').as_posix()}",
            "model_artifact_dir": str(tmp_path / "artifacts"),
            "event_bus": "memory",
            "llm_provider": "stub",
            "jwt_secret": SecretStr("integration-test-secret-value-1234567890"),
            "rate_limit_per_minute": 100000,
            "auth_rate_limit_per_minute": 100000,
        }
        base.update(overrides)
        return Settings(_env_file=None, **base)

    return factory


@pytest.fixture
async def app_container(
    make_settings: Callable[..., Settings],
) -> AsyncIterator[tuple[FastAPI, Container]]:
    app = create_app(make_settings())
    container: Container = app.state.container
    await container.startup()
    try:
        yield app, container
    finally:
        await container.shutdown()


@pytest.fixture
async def client(
    app_container: tuple[FastAPI, Container],
) -> AsyncIterator[httpx.AsyncClient]:
    app, _ = app_container
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http:
        yield http


@pytest.fixture
async def seeded(app_container: tuple[FastAPI, Container]) -> object:
    _, container = app_container
    return await seed_demo(container, log_path=HDFS_LOG, label_path=HDFS_LABELS)


@pytest.fixture
def login(client: httpx.AsyncClient) -> Callable[[str, str], Any]:
    async def _login(email: str, password: str) -> str:
        response = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        response.raise_for_status()
        token: str = response.json()["access_token"]
        return token

    return _login


@pytest.fixture
def bearer() -> Callable[[str], dict[str, str]]:
    def _header(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    return _header
