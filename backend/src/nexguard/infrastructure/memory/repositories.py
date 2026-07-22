"""In-memory repository adapters.

Implement the domain repository ports over plain dicts. Used by the ``memory``
backend and by use-case tests, so application logic can be exercised without a
database while honoring the exact same contracts as the SQLAlchemy adapters.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from nexguard.domain.entities import (
    Alert,
    Feedback,
    IncidentReport,
    Session,
    Template,
    User,
)


class InMemoryLogRepository:
    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}

    async def add_session(self, session: Session) -> Session:
        self._sessions[session.id] = session
        return session

    async def get_session(self, session_id: UUID) -> Session | None:
        return self._sessions.get(session_id)

    async def get_session_by_external_id(self, dataset: str, external_id: str) -> Session | None:
        return next(
            (
                s
                for s in self._sessions.values()
                if s.dataset == dataset and s.external_id == external_id
            ),
            None,
        )

    async def list_sessions(self, *, limit: int = 100, offset: int = 0) -> list[Session]:
        ordered = sorted(self._sessions.values(), key=lambda s: s.created_at, reverse=True)
        return ordered[offset : offset + limit]


class InMemoryAlertRepository:
    def __init__(self) -> None:
        self._alerts: dict[UUID, Alert] = {}

    async def add(self, alert: Alert) -> Alert:
        self._alerts[alert.id] = alert
        return alert

    async def get(self, alert_id: UUID) -> Alert | None:
        return self._alerts.get(alert_id)

    async def update(self, alert: Alert) -> Alert:
        self._alerts[alert.id] = alert
        return alert

    async def list(
        self,
        *,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Alert]:
        ordered = sorted(self._alerts.values(), key=lambda a: a.created_at, reverse=True)
        if severity is not None:
            ordered = [a for a in ordered if a.severity.value == severity]
        if status is not None:
            ordered = [a for a in ordered if a.status.value == status]
        return ordered[offset : offset + limit]


class InMemoryReportRepository:
    def __init__(self) -> None:
        self._by_alert: dict[UUID, IncidentReport] = {}

    async def add(self, report: IncidentReport) -> IncidentReport:
        self._by_alert[report.alert_id] = report
        return report

    async def get_by_alert(self, alert_id: UUID) -> IncidentReport | None:
        return self._by_alert.get(alert_id)


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._by_id: dict[UUID, User] = {}

    async def add(self, user: User) -> User:
        self._by_id[user.id] = user
        return user

    async def get(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    async def by_email(self, email: str) -> User | None:
        return next((u for u in self._by_id.values() if u.email == email.lower()), None)


class InMemoryFeedbackRepository:
    def __init__(self) -> None:
        self._items: list[Feedback] = []

    async def add(self, feedback: Feedback) -> Feedback:
        self._items.append(feedback)
        return feedback

    async def list_for_alert(self, alert_id: UUID) -> list[Feedback]:
        return [f for f in self._items if f.alert_id == alert_id]


class InMemoryTemplateRepository:
    def __init__(self) -> None:
        self._by_event_id: dict[int, Template] = {}

    async def upsert_many(self, templates: Sequence[Template]) -> None:
        for template in templates:
            self._by_event_id[int(template.event_id)] = template

    async def all(self) -> list[Template]:
        return [self._by_event_id[key] for key in sorted(self._by_event_id)]
