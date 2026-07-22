"""Analyst feedback + recalibration endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from nexguard.interfaces.api.deps import (
    AdminUser,
    AnalystUser,
    ContainerDep,
    SessionDep,
    ViewerUser,
)
from nexguard.interfaces.api.schemas import (
    CalibrationSnapshotOut,
    FeedbackOut,
    FeedbackRequest,
    FeedbackSummaryOut,
)

router = APIRouter(prefix="/api/v1", tags=["feedback"])


@router.post("/alerts/{alert_id}/feedback", response_model=FeedbackOut, status_code=201)
async def submit_feedback(
    alert_id: UUID,
    body: FeedbackRequest,
    user: AnalystUser,
    request: Request,
    container: ContainerDep,
    session: SessionDep,
) -> FeedbackOut:
    feedback = await container.submit_feedback(session).execute(
        alert_id=alert_id, analyst_id=user.id, label=body.label, note=body.note
    )
    await container.audit(session).record(
        actor_id=user.id,
        action="submit_feedback",
        resource=str(alert_id),
        ip=request.client.host if request.client else None,
        metadata={"label": body.label.value},
    )
    return FeedbackOut.from_entity(feedback)


@router.get("/alerts/{alert_id}/feedback", response_model=list[FeedbackOut])
async def list_feedback(
    alert_id: UUID, _user: ViewerUser, container: ContainerDep, session: SessionDep
) -> list[FeedbackOut]:
    items = await container.feedback(session).list_for_alert(alert_id)
    return [FeedbackOut.from_entity(item) for item in items]


@router.get("/feedback/summary", response_model=FeedbackSummaryOut)
async def feedback_summary(
    _user: ViewerUser, container: ContainerDep, session: SessionDep
) -> FeedbackSummaryOut:
    counts = await container.feedback(session).count_by_label()
    latest = await container.calibration(session).latest()
    return FeedbackSummaryOut(
        total=sum(counts.values()),
        counts=counts,
        latest_calibration=(
            CalibrationSnapshotOut.from_entity(latest) if latest is not None else None
        ),
    )


@router.get("/feedback/calibrations", response_model=list[CalibrationSnapshotOut])
async def list_calibrations(
    _user: ViewerUser, container: ContainerDep, session: SessionDep
) -> list[CalibrationSnapshotOut]:
    snapshots = await container.calibration(session).list()
    return [CalibrationSnapshotOut.from_entity(s) for s in snapshots]


@router.post("/feedback/recalibrate", response_model=CalibrationSnapshotOut, status_code=201)
async def recalibrate(
    user: AdminUser, request: Request, container: ContainerDep, session: SessionDep
) -> CalibrationSnapshotOut:
    snapshot = await container.recalibrate(session).execute()
    await container.audit(session).record(
        actor_id=user.id,
        action="recalibrate",
        resource="ensemble",
        ip=request.client.host if request.client else None,
        metadata={
            "threshold": snapshot.threshold,
            "precision_after": snapshot.precision_after,
        },
    )
    return CalibrationSnapshotOut.from_entity(snapshot)
