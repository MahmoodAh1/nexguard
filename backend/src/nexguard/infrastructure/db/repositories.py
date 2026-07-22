"""Repository adapters over an :class:`AsyncSession`.

These implement the domain repository ports. They add/flush but do **not** commit
— transaction boundaries are owned by the caller (the request-scoped session
dependency, or an explicit ``Database.session()`` scope), keeping a single
transaction per unit of work.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexguard.domain.entities import (
    Alert,
    Feedback,
    IncidentReport,
    Session,
    Template,
    User,
)
from nexguard.infrastructure.db import mappers
from nexguard.infrastructure.db.models import (
    AlertRow,
    AuditLogRow,
    FeedbackRow,
    IncidentReportRow,
    SessionRow,
    TemplateRow,
    UserRow,
)


class SqlAlchemyLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_session(self, session: Session) -> Session:
        self._session.add(mappers.session_to_row(session))
        await self._session.flush()
        return session

    async def get_session(self, session_id: UUID) -> Session | None:
        row = await self._session.get(
            SessionRow, session_id, options=[selectinload(SessionRow.events)]
        )
        return mappers.session_to_entity(row) if row else None

    async def get_session_by_external_id(self, dataset: str, external_id: str) -> Session | None:
        stmt = (
            select(SessionRow)
            .where(SessionRow.dataset == dataset, SessionRow.external_id == external_id)
            .options(selectinload(SessionRow.events))
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return mappers.session_to_entity(row) if row else None

    async def list_sessions(self, *, limit: int = 100, offset: int = 0) -> list[Session]:
        stmt = (
            select(SessionRow)
            .options(selectinload(SessionRow.events))
            .order_by(SessionRow.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [mappers.session_to_entity(row) for row in rows]


class SqlAlchemyAlertRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, alert: Alert) -> Alert:
        self._session.add(mappers.alert_to_row(alert))
        await self._session.flush()
        return alert

    async def get(self, alert_id: UUID) -> Alert | None:
        row = await self._session.get(AlertRow, alert_id)
        return mappers.alert_to_entity(row) if row else None

    async def update(self, alert: Alert) -> Alert:
        await self._session.merge(mappers.alert_to_row(alert))
        await self._session.flush()
        return alert

    async def list(
        self,
        *,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Alert]:
        stmt = select(AlertRow).order_by(AlertRow.created_at.desc())
        if severity is not None:
            stmt = stmt.where(AlertRow.severity == severity)
        if status is not None:
            stmt = stmt.where(AlertRow.status == status)
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [mappers.alert_to_entity(row) for row in rows]


class SqlAlchemyReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, report: IncidentReport) -> IncidentReport:
        self._session.add(mappers.report_to_row(report))
        await self._session.flush()
        return report

    async def get_by_alert(self, alert_id: UUID) -> IncidentReport | None:
        stmt = select(IncidentReportRow).where(IncidentReportRow.alert_id == alert_id).limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return mappers.report_to_entity(row) if row else None


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> User:
        self._session.add(mappers.user_to_row(user))
        await self._session.flush()
        return user

    async def get(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserRow, user_id)
        return mappers.user_to_entity(row) if row else None

    async def by_email(self, email: str) -> User | None:
        stmt = select(UserRow).where(UserRow.email == email.lower()).limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return mappers.user_to_entity(row) if row else None


class SqlAlchemyFeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, feedback: Feedback) -> Feedback:
        self._session.add(mappers.feedback_to_row(feedback))
        await self._session.flush()
        return feedback

    async def list_for_alert(self, alert_id: UUID) -> list[Feedback]:
        stmt = (
            select(FeedbackRow)
            .where(FeedbackRow.alert_id == alert_id)
            .order_by(FeedbackRow.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [mappers.feedback_to_entity(row) for row in rows]


class SqlAlchemyTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(self, templates: Sequence[Template]) -> None:
        if not templates:
            return
        existing_stmt = select(TemplateRow).where(
            TemplateRow.event_id.in_([int(t.event_id) for t in templates])
        )
        existing = {
            row.event_id: row
            for row in (await self._session.execute(existing_stmt)).scalars().all()
        }
        for template in templates:
            row = existing.get(int(template.event_id))
            if row is None:
                self._session.add(
                    TemplateRow(
                        event_id=int(template.event_id),
                        template=template.template,
                        occurrences=template.occurrences,
                        first_seen=template.first_seen,
                        last_seen=template.last_seen,
                    )
                )
            else:
                row.template = template.template
                row.occurrences = template.occurrences
                row.last_seen = template.last_seen
        await self._session.flush()

    async def all(self) -> list[Template]:
        stmt = select(TemplateRow).order_by(TemplateRow.event_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [mappers.template_to_entity(row) for row in rows]


class SqlAlchemyAuditLog:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        actor_id: UUID | None,
        action: str,
        resource: str,
        ip: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._session.add(
            AuditLogRow(
                actor_id=actor_id,
                action=action,
                resource=resource,
                ip=ip,
                meta=metadata or {},
            )
        )
        await self._session.flush()
