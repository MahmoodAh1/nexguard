"""API tests for Prometheus metrics exposition."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration


async def test_metrics_endpoint_exposes_recorded_http_metrics(
    client: httpx.AsyncClient,
) -> None:
    # Generate some traffic so the counters have samples.
    await client.get("/health")
    await client.get("/health")

    response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")

    body = response.text
    assert "nexguard_http_requests_total" in body
    assert "nexguard_http_request_duration_seconds" in body
    assert "nexguard_http_requests_in_progress" in body
    # The matched-route template is used as the label (not a raw/opaque path).
    assert 'path="/health"' in body


async def test_metrics_endpoint_is_unauthenticated(client: httpx.AsyncClient) -> None:
    # Prometheus scrapes without a bearer token.
    response = await client.get("/metrics")
    assert response.status_code == 200
