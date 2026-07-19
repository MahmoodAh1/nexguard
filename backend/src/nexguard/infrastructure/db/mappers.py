"""Translation between ORM rows and domain entities.

The domain never sees an ORM object; repositories map at the boundary. This keeps
the domain persistence-ignorant and lets the storage schema evolve independently.
"""

from __future__ import annotations

from datetime import UTC, datetime

from nexguard.domain.entities import (
    Alert,
    AlertStatus,
    Feedback,
    FeedbackLabel,
    IncidentReport,
    LogEvent,
    Session,
    Template,
    User,
    UserRole,
)
from nexguard.domain.evidence import Evidence
from nexguard.domain.report import IncidentReportPayload
from nexguard.domain.value_objects import EventId, Score, Severity
from nexguard.infrastructure.db.models import (
    AlertRow,
    FeedbackRow,
    IncidentReportRow,
    LogEventRow,
    SessionRow,
    TemplateRow,
    UserRow,
)


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; coerce them back to UTC-aware."""
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


# ── User ──
def user_to_row(user: User) -> UserRow:
    return UserRow(
        id=user.id,
        email=user.email,
        password_hash=user.password_hash,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


def user_to_entity(row: UserRow) -> User:
    return User(
        id=row.id,
        email=row.email,
        password_hash=row.password_hash,
        role=UserRole(row.role),
        is_active=row.is_active,
        created_at=_as_utc(row.created_at) or row.created_at,
    )


# ── Template ──
def template_to_entity(row: TemplateRow) -> Template:
    return Template(
        event_id=EventId(row.event_id),
        template=row.template,
        occurrences=row.occurrences,
        first_seen=_as_utc(row.first_seen) or row.first_seen,
        last_seen=_as_utc(row.last_seen) or row.last_seen,
    )


# ── Session + events ──
def session_to_row(session: Session) -> SessionRow:
    time_range = session.time_range
    return SessionRow(
        id=session.id,
        external_id=session.external_id,
        dataset=session.dataset,
        event_count=session.event_count,
        label=session.label,
        started_at=time_range.start if time_range else None,
        ended_at=time_range.end if time_range else None,
        created_at=session.created_at,
        events=[
            LogEventRow(
                event_id=int(event.event_id),
                raw=event.raw,
                line_no=event.line_no,
                params=dict(event.params),
                timestamp=event.timestamp,
            )
            for event in session.events
        ],
    )


def session_to_entity(row: SessionRow) -> Session:
    return Session(
        id=row.id,
        external_id=row.external_id,
        dataset=row.dataset,
        label=row.label,
        created_at=_as_utc(row.created_at) or row.created_at,
        events=[
            LogEvent(
                event_id=EventId(event.event_id),
                raw=event.raw,
                line_no=event.line_no,
                params=dict(event.params),
                timestamp=_as_utc(event.timestamp),
            )
            for event in sorted(row.events, key=lambda e: e.line_no)
        ],
    )


# ── Alert ──
def alert_to_row(alert: Alert) -> AlertRow:
    return AlertRow(
        id=alert.id,
        session_id=alert.session_id,
        run_id=alert.run_id,
        score=alert.score.value,
        severity=alert.severity.value,
        status=alert.status.value,
        evidence=alert.evidence.to_json_dict(),
        created_at=alert.created_at,
    )


def alert_to_entity(row: AlertRow) -> Alert:
    return Alert(
        id=row.id,
        session_id=row.session_id,
        run_id=row.run_id,
        score=Score(row.score),
        severity=Severity(row.severity),
        status=AlertStatus(row.status),
        evidence=Evidence.from_json_dict(dict(row.evidence)),
        created_at=_as_utc(row.created_at) or row.created_at,
    )


# ── Incident report ──
def report_to_row(report: IncidentReport) -> IncidentReportRow:
    return IncidentReportRow(
        id=report.id,
        alert_id=report.alert_id,
        model=report.model,
        payload=report.payload.model_dump(mode="json") if report.payload else None,
        verified=report.verified,
        rejected_reasons=list(report.rejected_reasons),
        created_at=report.created_at,
    )


def report_to_entity(row: IncidentReportRow) -> IncidentReport:
    payload = IncidentReportPayload.model_validate(row.payload) if row.payload else None
    return IncidentReport(
        id=row.id,
        alert_id=row.alert_id,
        model=row.model,
        payload=payload,
        verified=row.verified,
        rejected_reasons=list(row.rejected_reasons),
        created_at=_as_utc(row.created_at) or row.created_at,
    )


# ── Feedback ──
def feedback_to_row(feedback: Feedback) -> FeedbackRow:
    return FeedbackRow(
        id=feedback.id,
        alert_id=feedback.alert_id,
        analyst_id=feedback.analyst_id,
        label=feedback.label.value,
        note=feedback.note,
        created_at=feedback.created_at,
    )


def feedback_to_entity(row: FeedbackRow) -> Feedback:
    return Feedback(
        id=row.id,
        alert_id=row.alert_id,
        analyst_id=row.analyst_id,
        label=FeedbackLabel(row.label),
        note=row.note,
        created_at=_as_utc(row.created_at) or row.created_at,
    )
