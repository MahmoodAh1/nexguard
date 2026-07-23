"""API request/response schemas.

Wire-level Pydantic models, kept separate from domain entities so the transport
contract can evolve independently. Each response model maps from a domain entity
via a ``from_entity`` constructor.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from nexguard.domain.auth import TokenPair
from nexguard.domain.entities import (
    Alert,
    CalibrationSnapshot,
    Feedback,
    FeedbackLabel,
    IncidentReport,
    Session,
    Template,
    User,
)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

    @classmethod
    def from_pair(cls, pair: TokenPair) -> TokenResponse:
        return cls(
            access_token=pair.access_token,
            refresh_token=pair.refresh_token,
            token_type=pair.token_type,
            expires_in=pair.expires_in,
        )


class UserOut(BaseModel):
    id: UUID
    email: str
    role: str

    @classmethod
    def from_entity(cls, user: User) -> UserOut:
        return cls(id=user.id, email=user.email, role=user.role.value)


class AlertOut(BaseModel):
    id: UUID
    session_id: UUID
    session_external_id: str
    dataset: str
    severity: str
    status: str
    score: float
    event_count: int
    created_at: datetime

    @classmethod
    def from_entity(cls, alert: Alert) -> AlertOut:
        provenance = alert.evidence.provenance
        return cls(
            id=alert.id,
            session_id=alert.session_id,
            session_external_id=provenance.session_external_id,
            dataset=provenance.dataset,
            severity=alert.severity.value,
            status=alert.status.value,
            score=round(alert.score.value, 4),
            event_count=provenance.event_count,
            created_at=alert.created_at,
        )


class AlertDetailOut(AlertOut):
    evidence: dict[str, object]

    @classmethod
    def from_entity(cls, alert: Alert) -> AlertDetailOut:
        base = AlertOut.from_entity(alert)
        return cls(**base.model_dump(), evidence=alert.evidence.to_json_dict())


class ReportOut(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    id: UUID
    alert_id: UUID
    model: str
    verified: bool
    rejected_reasons: list[str]
    payload: dict[str, object] | None
    created_at: datetime

    @classmethod
    def from_entity(cls, report: IncidentReport) -> ReportOut:
        return cls(
            id=report.id,
            alert_id=report.alert_id,
            model=report.model,
            verified=report.verified,
            rejected_reasons=list(report.rejected_reasons),
            payload=report.payload.model_dump(mode="json") if report.payload else None,
            created_at=report.created_at,
        )


class DetectionRunOut(BaseModel):
    alerted: bool
    alert: AlertDetailOut | None

    @classmethod
    def from_alert(cls, alert: Alert | None) -> DetectionRunOut:
        return cls(
            alerted=alert is not None,
            alert=AlertDetailOut.from_entity(alert) if alert is not None else None,
        )


class FeedbackRequest(BaseModel):
    label: FeedbackLabel
    note: str | None = Field(default=None, max_length=2000)


class FeedbackOut(BaseModel):
    id: UUID
    alert_id: UUID
    analyst_id: UUID
    label: str
    note: str | None
    created_at: datetime

    @classmethod
    def from_entity(cls, feedback: Feedback) -> FeedbackOut:
        return cls(
            id=feedback.id,
            alert_id=feedback.alert_id,
            analyst_id=feedback.analyst_id,
            label=feedback.label.value,
            note=feedback.note,
            created_at=feedback.created_at,
        )


class CalibrationSnapshotOut(BaseModel):
    id: UUID
    threshold: float
    seq_weight: float
    stat_weight: float
    feedback_count: int
    precision_before: float
    recall_before: float
    precision_after: float
    recall_after: float
    created_at: datetime

    @classmethod
    def from_entity(cls, snapshot: CalibrationSnapshot) -> CalibrationSnapshotOut:
        return cls(
            id=snapshot.id,
            threshold=round(snapshot.threshold, 4),
            seq_weight=snapshot.seq_weight,
            stat_weight=snapshot.stat_weight,
            feedback_count=snapshot.feedback_count,
            precision_before=round(snapshot.precision_before, 4),
            recall_before=round(snapshot.recall_before, 4),
            precision_after=round(snapshot.precision_after, 4),
            recall_after=round(snapshot.recall_after, 4),
            created_at=snapshot.created_at,
        )


class FeedbackSummaryOut(BaseModel):
    total: int
    counts: dict[str, int]
    latest_calibration: CalibrationSnapshotOut | None


class HealthOut(BaseModel):
    status: str
    version: str
    environment: str
    detectors_loaded: bool
    llm_provider: str
    event_bus: str


class SystemMetricsOut(BaseModel):
    cpu_percent: float
    memory_used_mb: float
    memory_percent: float
    process_rss_mb: float


# ── Log Explorer ──
class LogEventOut(BaseModel):
    event_id: int
    raw: str
    line_no: int
    timestamp: datetime | None


class SessionSummaryOut(BaseModel):
    id: UUID
    external_id: str
    dataset: str
    event_count: int
    label: bool | None
    created_at: datetime

    @classmethod
    def from_entity(cls, session: Session) -> SessionSummaryOut:
        return cls(
            id=session.id,
            external_id=session.external_id,
            dataset=session.dataset,
            event_count=session.event_count,
            label=session.label,
            created_at=session.created_at,
        )


class SessionDetailOut(SessionSummaryOut):
    events: list[LogEventOut]

    @classmethod
    def from_entity(cls, session: Session) -> SessionDetailOut:
        base = SessionSummaryOut.from_entity(session)
        return cls(
            **base.model_dump(),
            events=[
                LogEventOut(
                    event_id=int(event.event_id),
                    raw=event.raw,
                    line_no=event.line_no,
                    timestamp=event.timestamp,
                )
                for event in session.events
            ],
        )


class TemplateOut(BaseModel):
    event_id: int
    template: str
    occurrences: int

    @classmethod
    def from_entity(cls, template: Template) -> TemplateOut:
        return cls(
            event_id=int(template.event_id),
            template=template.template,
            occurrences=template.occurrences,
        )


# ── Detection Analytics ──
class ScoreBucket(BaseModel):
    lower: float
    upper: float
    count: int


class AnalyticsSummaryOut(BaseModel):
    total_alerts: int
    by_severity: dict[str, int]
    by_status: dict[str, int]
    score_histogram: list[ScoreBucket]
    seq_weight: float
    stat_weight: float
    threshold: float
    detectors_loaded: bool
    latest_calibration: CalibrationSnapshotOut | None


# ── Configuration ──
class ConfigOut(BaseModel):
    seq_weight: float
    stat_weight: float
    threshold: float
    detectors_loaded: bool
    llm_provider: str
    model_name: str


class ConfigUpdateRequest(BaseModel):
    seq_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    stat_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
