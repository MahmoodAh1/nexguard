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
from nexguard.domain.entities import Alert, IncidentReport, User


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


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
