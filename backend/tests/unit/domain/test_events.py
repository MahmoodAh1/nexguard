"""Unit tests for domain events and their transport payloads.

Regression guard: ``@dataclass(slots=True)`` rebuilds the class, which breaks
zero-argument ``super()`` on Python < 3.14 (``TypeError: super(type, obj) ...``).
These tests exercise ``to_payload`` on every event subclass so that footgun can
never slip through CI again — it surfaced only under the 3.12 runner, not 3.13+.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from nexguard.domain.events import AlertCreated, DomainEvent, ReportGenerated
from nexguard.domain.value_objects import Severity


def test_base_event_payload_has_transport_fields() -> None:
    event = DomainEvent()
    payload = event.to_payload()
    assert payload["topic"] == "domain.event"
    assert payload["event_id"] == str(event.event_id)
    assert payload["occurred_at"] == event.occurred_at.isoformat()


def test_alert_created_payload_merges_base_and_own_fields() -> None:
    alert_id = uuid4()
    event = AlertCreated(
        alert_id=alert_id,
        session_external_id="blk_-123",
        severity=Severity.CRITICAL,
        score=0.97,
    )

    payload = event.to_payload()

    # Base fields survive the super() merge (the slots+super regression path).
    assert payload["topic"] == "alert.created"
    assert payload["event_id"] == str(event.event_id)
    assert payload["occurred_at"] == event.occurred_at.isoformat()
    # Subclass fields.
    assert payload["alert_id"] == str(alert_id)
    assert payload["session_external_id"] == "blk_-123"
    assert payload["severity"] == "critical"
    assert payload["score"] == 0.97
    # Payload is JSON-safe: no raw UUID/datetime/enum leaks through.
    assert not any(isinstance(v, (UUID, Severity)) for v in payload.values())


def test_report_generated_payload_merges_base_and_own_fields() -> None:
    alert_id, report_id = uuid4(), uuid4()
    event = ReportGenerated(alert_id=alert_id, report_id=report_id, verified=True)

    payload = event.to_payload()

    assert payload["topic"] == "report.generated"
    assert payload["event_id"] == str(event.event_id)
    assert payload["alert_id"] == str(alert_id)
    assert payload["report_id"] == str(report_id)
    assert payload["verified"] is True
