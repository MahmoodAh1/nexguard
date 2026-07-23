"""Domain events published on the :class:`~nexguard.domain.ports.EventBus`.

Each event knows its topic and can serialize to a JSON-safe payload, which the
API bridges to browser WebSocket clients for live updates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID, uuid4

from nexguard.domain.value_objects import Severity


def _now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base class for domain events."""

    topic: ClassVar[str] = "domain.event"
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=_now)

    def to_payload(self) -> dict[str, object]:
        """A JSON-safe representation for transport over the bus / WebSocket."""
        return {
            "topic": self.topic,
            "event_id": str(self.event_id),
            "occurred_at": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class AlertCreated(DomainEvent):
    """A new alert was raised by the detection pipeline."""

    topic: ClassVar[str] = "alert.created"
    alert_id: UUID = field(default_factory=uuid4)
    session_external_id: str = ""
    severity: Severity = Severity.LOW
    score: float = 0.0

    def to_payload(self) -> dict[str, object]:
        # Explicit two-arg super(): @dataclass(slots=True) rebuilds the class, so
        # zero-arg super()'s implicit __class__ cell points at the pre-slots class
        # and raises TypeError on Python < 3.14. Naming the class resolves it at
        # call time on every interpreter version.
        return {
            **super(AlertCreated, self).to_payload(),
            "alert_id": str(self.alert_id),
            "session_external_id": self.session_external_id,
            "severity": self.severity.value,
            "score": self.score,
        }


@dataclass(frozen=True, slots=True)
class ReportGenerated(DomainEvent):
    """An incident report finished generation (verified or rejected)."""

    topic: ClassVar[str] = "report.generated"
    alert_id: UUID = field(default_factory=uuid4)
    report_id: UUID = field(default_factory=uuid4)
    verified: bool = False

    def to_payload(self) -> dict[str, object]:
        # See AlertCreated.to_payload — explicit super() for slots+super safety.
        return {
            **super(ReportGenerated, self).to_payload(),
            "alert_id": str(self.alert_id),
            "report_id": str(self.report_id),
            "verified": self.verified,
        }
