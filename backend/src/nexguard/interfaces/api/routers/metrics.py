"""Observability endpoints: Prometheus scrape + JSON system metrics."""

from __future__ import annotations

import psutil
from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from nexguard.interfaces.api.deps import ViewerUser
from nexguard.interfaces.api.schemas import SystemMetricsOut

# Unauthenticated Prometheus scrape endpoint (exempt from auth + rate limiting).
scrape_router = APIRouter(tags=["observability"])


@scrape_router.get("/metrics")
async def prometheus_metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Authenticated JSON metrics for the Live Monitoring page.
router = APIRouter(prefix="/api/v1/metrics", tags=["observability"])


@router.get("/system", response_model=SystemMetricsOut)
async def system_metrics(_user: ViewerUser) -> SystemMetricsOut:
    virtual_memory = psutil.virtual_memory()
    process = psutil.Process()
    return SystemMetricsOut(
        cpu_percent=psutil.cpu_percent(interval=None),
        memory_used_mb=round(virtual_memory.used / 1e6, 2),
        memory_percent=virtual_memory.percent,
        process_rss_mb=round(process.memory_info().rss / 1e6, 2),
    )
