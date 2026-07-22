"""Domain entities.

Entities have identity (a stable ``id``) and, unlike value objects, may change
over their lifecycle (an :class:`Alert` moves through statuses). They are modeled
as dataclasses: identity-based rather than value-based, with behavior attached
where the domain has rules (e.g. legal alert-status transitions).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from nexguard.domain.errors import ValidationError
from nexguard.domain.evidence import Evidence
from nexguard.domain.report import IncidentReportPayload
from nexguard.domain.value_objects import EventId, Score, Severity, TimeRange


def _now() -> datetime:
    return datetime.now(tz=UTC)


class UserRole(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

    @property
    def rank(self) -> int:
        return {UserRole.VIEWER: 0, UserRole.ANALYST: 1, UserRole.ADMIN: 2}[self]

    def satisfies(self, required: UserRole) -> bool:
        """Role hierarchy: a higher role satisfies any lower requirement."""
        return self.rank >= required.rank


class AlertStatus(StrEnum):
    NEW = "new"
    TRIAGED = "triaged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class FeedbackLabel(StrEnum):
    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    BENIGN = "benign"
    UNKNOWN = "unknown"


class DatasetKind(StrEnum):
    HDFS = "hdfs"
    BGL = "bgl"
    CICIDS = "cicids"


# Legal alert lifecycle transitions (see docs/architecture/data-model.md).
_ALLOWED_TRANSITIONS: dict[AlertStatus, frozenset[AlertStatus]] = {
    AlertStatus.NEW: frozenset({AlertStatus.TRIAGED, AlertStatus.DISMISSED}),
    AlertStatus.TRIAGED: frozenset(
        {AlertStatus.INVESTIGATING, AlertStatus.DISMISSED, AlertStatus.RESOLVED}
    ),
    AlertStatus.INVESTIGATING: frozenset({AlertStatus.RESOLVED, AlertStatus.DISMISSED}),
    AlertStatus.RESOLVED: frozenset(),
    AlertStatus.DISMISSED: frozenset(),
}


@dataclass(slots=True)
class Template:
    """A mined log template with a stable :class:`EventId`."""

    event_id: EventId
    template: str
    occurrences: int = 0
    first_seen: datetime = field(default_factory=_now)
    last_seen: datetime = field(default_factory=_now)


@dataclass(slots=True)
class LogEvent:
    """A single parsed log line within a session."""

    event_id: EventId
    raw: str
    line_no: int
    params: dict[str, str] = field(default_factory=dict)
    timestamp: datetime | None = None


@dataclass(slots=True)
class Session:
    """An ordered sequence of log events sharing a session key (HDFS ``block_id``).

    The unit of detection. Exposes both representations the detection pipeline
    needs: the ordered event-id sequence (for the sequence model) and event
    counts (for the statistical model).
    """

    external_id: str
    dataset: str
    events: list[LogEvent] = field(default_factory=list)
    label: bool | None = None  # ground truth, only for evaluation datasets
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)

    def event_id_sequence(self) -> list[EventId]:
        return [event.event_id for event in self.events]

    def event_counts(self) -> dict[EventId, int]:
        return dict(Counter(event.event_id for event in self.events))

    def unique_event_ids(self) -> set[EventId]:
        return {event.event_id for event in self.events}

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def time_range(self) -> TimeRange | None:
        return TimeRange.spanning(e.timestamp for e in self.events if e.timestamp)


@dataclass(slots=True)
class DetectionRun:
    """One scoring pass over a session by the detection pipeline."""

    session_id: UUID
    model_versions: dict[str, str] = field(default_factory=dict)
    latency_ms: float = 0.0
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class Alert:
    """A prioritized, explainable detection result."""

    session_id: UUID
    score: Score
    severity: Severity
    evidence: Evidence
    run_id: UUID | None = None
    status: AlertStatus = AlertStatus.NEW
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)

    def transition_to(self, new_status: AlertStatus) -> None:
        allowed = _ALLOWED_TRANSITIONS[self.status]
        if new_status not in allowed:
            raise ValidationError(
                f"illegal alert transition {self.status.value} -> {new_status.value}"
            )
        self.status = new_status


@dataclass(slots=True)
class IncidentReport:
    """A generated incident report and its verification outcome.

    Rejected reports are still persisted (with ``verified=False`` and reasons) for
    auditability — a rejection is an observable event, never silent.
    """

    alert_id: UUID
    model: str
    payload: IncidentReportPayload | None = None
    verified: bool = False
    rejected_reasons: list[str] = field(default_factory=list)
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class User:
    """An authenticated principal with an RBAC role."""

    email: str
    password_hash: str
    role: UserRole = UserRole.VIEWER
    is_active: bool = True
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)

    def deactivate(self) -> None:
        self.is_active = False


@dataclass(slots=True)
class Feedback:
    """An analyst's label on an alert, feeding recalibration."""

    alert_id: UUID
    analyst_id: UUID
    label: FeedbackLabel
    note: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)


@dataclass(slots=True)
class CalibrationSnapshot:
    """A recalibration outcome: the operating point + before/after quality.

    Produced when analyst feedback is folded back in. Both the before and after
    precision/recall are recorded so the improvement is auditable.
    """

    threshold: float
    seq_weight: float
    stat_weight: float
    feedback_count: int
    precision_before: float
    recall_before: float
    precision_after: float
    recall_after: float
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
