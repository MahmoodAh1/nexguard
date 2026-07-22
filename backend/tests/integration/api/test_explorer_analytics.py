"""API tests for Log Explorer, Detection Analytics, and Configuration."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


async def test_log_explorer_sessions_and_templates(
    client: httpx.AsyncClient,
    seeded: object,
    creds: SimpleNamespace,
    login: Callable[[str, str], Any],
    bearer: Callable[[str], dict[str, str]],
) -> None:
    viewer = bearer(await login(*creds.viewer))

    sessions = (await client.get("/api/v1/sessions", headers=viewer)).json()
    assert sessions
    assert {"external_id", "dataset", "event_count"} <= set(sessions[0])

    detail = await client.get(f"/api/v1/sessions/{sessions[0]['id']}", headers=viewer)
    assert detail.status_code == 200
    assert detail.json()["events"]  # parsed log events present

    templates = (await client.get("/api/v1/templates", headers=viewer)).json()
    assert templates
    assert templates[0]["template"]

    missing = await client.get(
        "/api/v1/sessions/00000000-0000-0000-0000-000000000000", headers=viewer
    )
    assert missing.status_code == 404


async def test_analytics_summary(
    client: httpx.AsyncClient,
    seeded: object,
    creds: SimpleNamespace,
    login: Callable[[str, str], Any],
    bearer: Callable[[str], dict[str, str]],
) -> None:
    viewer = bearer(await login(*creds.viewer))
    summary = (await client.get("/api/v1/analytics/summary", headers=viewer)).json()

    assert summary["total_alerts"] > 0
    assert summary["by_severity"].get("high", 0) > 0
    assert len(summary["score_histogram"]) == 10
    assert 0.0 <= summary["threshold"] <= 1.0
    assert summary["detectors_loaded"] is True


async def test_configuration_read_and_admin_update(
    client: httpx.AsyncClient,
    seeded: object,
    creds: SimpleNamespace,
    login: Callable[[str, str], Any],
    bearer: Callable[[str], dict[str, str]],
) -> None:
    viewer = bearer(await login(*creds.viewer))
    admin = bearer(await login(*creds.admin))

    current = (await client.get("/api/v1/config", headers=viewer)).json()
    assert {"seq_weight", "stat_weight", "threshold"} <= set(current)

    # Admin raises the threshold.
    updated = await client.put("/api/v1/config", headers=admin, json={"threshold": 0.7})
    assert updated.status_code == 200
    assert updated.json()["threshold"] == pytest.approx(0.7)

    # The change is reflected on read.
    reread = (await client.get("/api/v1/config", headers=viewer)).json()
    assert reread["threshold"] == pytest.approx(0.7)

    # Viewer cannot update config.
    denied = await client.put("/api/v1/config", headers=viewer, json={"threshold": 0.3})
    assert denied.status_code == 403
