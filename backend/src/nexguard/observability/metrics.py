"""Prometheus metrics.

Defined once on the default registry and exported by ``GET /metrics``. HTTP
metrics are recorded by middleware; domain metrics (alerts, reports, detection
latency) are recorded at the interface boundary so the domain/application layers
stay free of the metrics library.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "nexguard_http_requests_total",
    "Total HTTP requests.",
    labelnames=("method", "path", "status"),
)

HTTP_LATENCY = Histogram(
    "nexguard_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    labelnames=("method", "path"),
)

HTTP_IN_PROGRESS = Gauge(
    "nexguard_http_requests_in_progress",
    "In-flight HTTP requests.",
)

ALERTS_TOTAL = Counter(
    "nexguard_alerts_total",
    "Alerts raised by the detection pipeline.",
    labelnames=("severity",),
)

REPORTS_TOTAL = Counter(
    "nexguard_incident_reports_total",
    "Incident reports generated.",
    labelnames=("verified",),
)

DETECTION_LATENCY = Histogram(
    "nexguard_detection_duration_seconds",
    "Detection scoring latency in seconds (per session).",
)


def record_alert(severity: str) -> None:
    ALERTS_TOTAL.labels(severity=severity).inc()


def record_report(*, verified: bool) -> None:
    REPORTS_TOTAL.labels(verified=str(verified).lower()).inc()
