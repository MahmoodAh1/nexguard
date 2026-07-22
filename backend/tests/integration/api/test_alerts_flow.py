"""End-to-end API flow over seeded data: explore -> report -> detect."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


async def test_alert_exploration_and_report_generation(
    client: httpx.AsyncClient,
    seeded: object,
    creds: SimpleNamespace,
    login: Callable[[str, str], Any],
    bearer: Callable[[str], dict[str, str]],
) -> None:
    viewer = await login(*creds.viewer)
    analyst = await login(*creds.analyst)

    # List + filter alerts.
    listing = await client.get(
        "/api/v1/alerts", headers=bearer(viewer), params={"severity": "high"}
    )
    assert listing.status_code == 200
    alerts = listing.json()
    assert alerts, "seed produced high-severity alerts"
    alert_id = alerts[0]["id"]

    # Alert detail carries the full explainability evidence.
    detail = await client.get(f"/api/v1/alerts/{alert_id}", headers=bearer(viewer))
    assert detail.status_code == 200
    evidence = detail.json()["evidence"]
    assert (
        "sequence" in evidence and "statistical" in evidence and "ensemble" in evidence
    )

    # Analyst generates a verified incident report.
    generated = await client.post(
        f"/api/v1/alerts/{alert_id}/report", headers=bearer(analyst)
    )
    assert generated.status_code == 201
    report = generated.json()
    assert report["verified"] is True
    assert report["payload"]["mitre_hypotheses"]
    assert all(h["is_hypothesis"] for h in report["payload"]["mitre_hypotheses"])

    # And can fetch it back.
    fetched = await client.get(
        f"/api/v1/alerts/{alert_id}/report", headers=bearer(viewer)
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == report["id"]


async def test_detection_run_endpoint(
    client: httpx.AsyncClient,
    seeded: object,
    creds: SimpleNamespace,
    login: Callable[[str, str], Any],
    bearer: Callable[[str], dict[str, str]],
) -> None:
    analyst = await login(*creds.analyst)
    alerts = (await client.get("/api/v1/alerts", headers=bearer(analyst))).json()
    session_id = alerts[0]["session_id"]

    response = await client.post(
        f"/api/v1/detection/sessions/{session_id}/run", headers=bearer(analyst)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["alerted"] is True
    assert body["alert"]["severity"] in {"medium", "high", "critical"}


async def test_unknown_alert_is_404(
    client: httpx.AsyncClient,
    seeded: object,
    creds: SimpleNamespace,
    login: Callable[[str, str], Any],
    bearer: Callable[[str], dict[str, str]],
) -> None:
    viewer = await login(*creds.viewer)
    response = await client.get(
        "/api/v1/alerts/00000000-0000-0000-0000-000000000000",
        headers=bearer(viewer),
    )
    assert response.status_code == 404
