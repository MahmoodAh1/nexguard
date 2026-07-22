"""Alert exploration and incident-report endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request

from nexguard.domain.errors import NotFoundError
from nexguard.interfaces.api.deps import (
    AnalystUser,
    ContainerDep,
    SessionDep,
    ViewerUser,
)
from nexguard.interfaces.api.schemas import AlertDetailOut, AlertOut, ReportOut

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    _user: ViewerUser,
    container: ContainerDep,
    session: SessionDep,
    severity: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AlertOut]:
    alerts = await container.alerts(session).list(
        severity=severity, status=status, limit=limit, offset=offset
    )
    return [AlertOut.from_entity(alert) for alert in alerts]


@router.get("/{alert_id}", response_model=AlertDetailOut)
async def get_alert(
    alert_id: UUID, _user: ViewerUser, container: ContainerDep, session: SessionDep
) -> AlertDetailOut:
    alert = await container.alerts(session).get(alert_id)
    if alert is None:
        raise NotFoundError("Alert", alert_id)
    return AlertDetailOut.from_entity(alert)


@router.post("/{alert_id}/report", response_model=ReportOut, status_code=201)
async def generate_report(
    alert_id: UUID,
    user: AnalystUser,
    request: Request,
    container: ContainerDep,
    session: SessionDep,
    regenerate: Annotated[bool, Query()] = False,
) -> ReportOut:
    report = await container.generate_report(session).execute(alert_id, regenerate=regenerate)
    await container.audit(session).record(
        actor_id=user.id,
        action="generate_report",
        resource=str(alert_id),
        ip=request.client.host if request.client else None,
        metadata={"verified": report.verified},
    )
    return ReportOut.from_entity(report)


@router.get("/{alert_id}/report", response_model=ReportOut)
async def get_report(
    alert_id: UUID, _user: ViewerUser, container: ContainerDep, session: SessionDep
) -> ReportOut:
    report = await container.reports(session).get_by_alert(alert_id)
    if report is None:
        raise NotFoundError("IncidentReport", alert_id)
    return ReportOut.from_entity(report)
