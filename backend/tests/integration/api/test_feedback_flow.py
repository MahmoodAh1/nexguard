"""API tests for the feedback loop + recalibration endpoints."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


async def _first_alert_id(client: httpx.AsyncClient, headers: dict[str, str]) -> str:
    alerts = (await client.get("/api/v1/alerts", headers=headers)).json()
    return str(alerts[0]["id"])


async def test_analyst_labels_and_admin_recalibrates(
    client: httpx.AsyncClient,
    seeded: object,
    creds: SimpleNamespace,
    login: Callable[[str, str], Any],
    bearer: Callable[[str], dict[str, str]],
) -> None:
    analyst = bearer(await login(*creds.analyst))
    admin = bearer(await login(*creds.admin))

    alert_id = await _first_alert_id(client, analyst)

    # Analyst labels the alert a true positive.
    submitted = await client.post(
        f"/api/v1/alerts/{alert_id}/feedback",
        headers=analyst,
        json={"label": "true_positive", "note": "confirmed incident"},
    )
    assert submitted.status_code == 201
    assert submitted.json()["label"] == "true_positive"

    # It appears in the alert's feedback and the global summary.
    listing = await client.get(f"/api/v1/alerts/{alert_id}/feedback", headers=analyst)
    assert listing.status_code == 200 and len(listing.json()) == 1

    summary = (await client.get("/api/v1/feedback/summary", headers=analyst)).json()
    assert summary["total"] >= 1
    assert summary["counts"].get("true_positive", 0) >= 1

    # Admin recalibrates from the feedback.
    recal = await client.post("/api/v1/feedback/recalibrate", headers=admin)
    assert recal.status_code == 201
    body = recal.json()
    assert body["feedback_count"] >= 1
    assert 0.0 <= body["precision_after"] <= 1.0
    assert 0.0 <= body["threshold"] <= 1.0

    # The snapshot is now the latest calibration.
    summary2 = (await client.get("/api/v1/feedback/summary", headers=admin)).json()
    assert summary2["latest_calibration"]["id"] == body["id"]


async def test_feedback_rbac(
    client: httpx.AsyncClient,
    seeded: object,
    creds: SimpleNamespace,
    login: Callable[[str, str], Any],
    bearer: Callable[[str], dict[str, str]],
) -> None:
    viewer = bearer(await login(*creds.viewer))
    analyst = bearer(await login(*creds.analyst))
    alert_id = await _first_alert_id(client, viewer)

    # Viewer cannot submit feedback.
    denied = await client.post(
        f"/api/v1/alerts/{alert_id}/feedback",
        headers=viewer,
        json={"label": "false_positive"},
    )
    assert denied.status_code == 403

    # Analyst cannot recalibrate (admin only).
    denied_recal = await client.post("/api/v1/feedback/recalibrate", headers=analyst)
    assert denied_recal.status_code == 403
