"""On-demand detection endpoint.

Re-scores an already-ingested session through the live detection pipeline. When
it raises an alert, an ``AlertCreated`` event is published on the bus and streamed
to connected dashboards — the visible, real-time path of the platform.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status

from nexguard.domain.errors import NotFoundError
from nexguard.interfaces.api.deps import AnalystUser, ContainerDep, SessionDep
from nexguard.interfaces.api.schemas import DetectionRunOut

router = APIRouter(prefix="/api/v1/detection", tags=["detection"])


@router.post("/sessions/{session_id}/run", response_model=DetectionRunOut)
async def run_detection(
    session_id: UUID,
    user: AnalystUser,
    request: Request,
    container: ContainerDep,
    session: SessionDep,
) -> DetectionRunOut:
    use_case = container.detect_anomalies(session)
    if use_case is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="detection models are not loaded; train and seed artifacts first",
        )
    target = await container.logs(session).get_session(session_id)
    if target is None:
        raise NotFoundError("Session", session_id)

    alert = await use_case.execute(target)
    await container.audit(session).record(
        actor_id=user.id,
        action="run_detection",
        resource=str(session_id),
        ip=request.client.host if request.client else None,
        metadata={"alerted": alert is not None},
    )
    return DetectionRunOut.from_alert(alert)
