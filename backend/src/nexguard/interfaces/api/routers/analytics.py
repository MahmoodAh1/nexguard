"""Detection Analytics: aggregate alert stats + current detection configuration."""

from __future__ import annotations

from fastapi import APIRouter

from nexguard.interfaces.api.deps import ContainerDep, SessionDep, ViewerUser
from nexguard.interfaces.api.schemas import (
    AnalyticsSummaryOut,
    CalibrationSnapshotOut,
    ScoreBucket,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

_BUCKETS = 10


@router.get("/summary", response_model=AnalyticsSummaryOut)
async def summary(
    _user: ViewerUser, container: ContainerDep, session: SessionDep
) -> AnalyticsSummaryOut:
    alerts = container.alerts(session)
    recent = await alerts.list(limit=500)
    latest = await container.calibration(session).latest()
    runtime = container.runtime

    return AnalyticsSummaryOut(
        total_alerts=await alerts.total(),
        by_severity=await alerts.severity_counts(),
        by_status=await alerts.status_counts(),
        score_histogram=_histogram([a.score.value for a in recent]),
        seq_weight=runtime.seq_weight,
        stat_weight=runtime.stat_weight,
        threshold=runtime.threshold,
        detectors_loaded=container.detectors is not None,
        latest_calibration=(
            CalibrationSnapshotOut.from_entity(latest) if latest is not None else None
        ),
    )


def _histogram(scores: list[float]) -> list[ScoreBucket]:
    counts = [0] * _BUCKETS
    for score in scores:
        index = min(_BUCKETS - 1, int(score * _BUCKETS))
        counts[index] += 1
    return [
        ScoreBucket(lower=i / _BUCKETS, upper=(i + 1) / _BUCKETS, count=count)
        for i, count in enumerate(counts)
    ]
