"""SQLAlchemy 2.0 ORM models.

Cross-dialect by design: :class:`sqlalchemy.Uuid` stores native ``UUID`` on
PostgreSQL and ``CHAR(32)`` elsewhere; generic ``JSON`` maps to ``JSONB`` on
PostgreSQL (via a variant) and ``JSON`` on SQLite. Timestamps are timezone-aware.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# JSONB on Postgres, JSON everywhere else.
JsonType = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(tz=UTC)


class Base(DeclarativeBase):
    """Declarative base for all NexGuard tables."""


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class TemplateRow(Base):
    __tablename__ = "templates"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    event_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    template: Mapped[str] = mapped_column(Text)
    occurrences: Mapped[int] = mapped_column(Integer, default=0)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    dataset: Mapped[str] = mapped_column(String(32), index=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    events: Mapped[list[LogEventRow]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="LogEventRow.line_no",
        lazy="selectin",
    )


class LogEventRow(Base):
    __tablename__ = "log_events"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[int] = mapped_column(Integer, index=True)
    raw: Mapped[str] = mapped_column(Text)
    line_no: Mapped[int] = mapped_column(Integer)
    params: Mapped[dict[str, str]] = mapped_column(JsonType, default=dict)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    session: Mapped[SessionRow] = relationship(back_populates="events")


class DetectionRunRow(Base):
    __tablename__ = "detection_runs"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id"), index=True)
    model_versions: Mapped[dict[str, str]] = mapped_column(JsonType, default=dict)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AlertRow(Base):
    __tablename__ = "alerts"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(ForeignKey("sessions.id"), index=True)
    run_id: Mapped[UUID | None] = mapped_column(Uuid(), nullable=True)
    score: Mapped[float] = mapped_column(Float, index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="new", index=True)
    evidence: Mapped[dict[str, object]] = mapped_column(JsonType)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class IncidentReportRow(Base):
    __tablename__ = "incident_reports"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    alert_id: Mapped[UUID] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), unique=True, index=True
    )
    model: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict[str, object] | None] = mapped_column(JsonType, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    rejected_reasons: Mapped[list[str]] = mapped_column(JsonType, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class FeedbackRow(Base):
    __tablename__ = "feedback"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    alert_id: Mapped[UUID] = mapped_column(ForeignKey("alerts.id"), index=True)
    analyst_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    label: Mapped[str] = mapped_column(String(24))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLogRow(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(Uuid(), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource: Mapped[str] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict[str, object]] = mapped_column("metadata", JsonType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)


class CalibrationSnapshotRow(Base):
    __tablename__ = "calibration_snapshots"

    id: Mapped[UUID] = mapped_column(Uuid(), primary_key=True, default=uuid4)
    threshold: Mapped[float] = mapped_column(Float)
    seq_weight: Mapped[float] = mapped_column(Float)
    stat_weight: Mapped[float] = mapped_column(Float)
    feedback_count: Mapped[int] = mapped_column(Integer)
    precision_before: Mapped[float] = mapped_column(Float)
    recall_before: Mapped[float] = mapped_column(Float)
    precision_after: Mapped[float] = mapped_column(Float)
    recall_after: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
