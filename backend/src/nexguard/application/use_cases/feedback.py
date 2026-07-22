"""Analyst feedback loop and recalibration.

Analysts label alerts (true positive / false positive / benign / unknown). Those
labels are the operator's ground truth, and recalibration folds them back in:
it computes the current precision/recall on the labeled alerts, searches for a
better decision threshold, applies it to the runtime config, and persists a
snapshot recording the before/after improvement.
"""

from __future__ import annotations

from uuid import UUID

from nexguard.config.runtime import RuntimeConfig
from nexguard.domain.entities import CalibrationSnapshot, Feedback, FeedbackLabel
from nexguard.domain.errors import NotFoundError, ValidationError
from nexguard.domain.ports import (
    AlertRepository,
    CalibrationRepository,
    FeedbackRepository,
)
from nexguard.evaluation.calibration import sweep_threshold
from nexguard.evaluation.metrics import compute_metrics


class SubmitFeedback:
    """Record an analyst's label on an alert."""

    def __init__(self, feedback_repo: FeedbackRepository, alert_repo: AlertRepository) -> None:
        self._feedback = feedback_repo
        self._alerts = alert_repo

    async def execute(
        self,
        *,
        alert_id: UUID,
        analyst_id: UUID,
        label: FeedbackLabel,
        note: str | None = None,
    ) -> Feedback:
        if await self._alerts.get(alert_id) is None:
            raise NotFoundError("Alert", alert_id)
        return await self._feedback.add(
            Feedback(alert_id=alert_id, analyst_id=analyst_id, label=label, note=note)
        )


class Recalibrate:
    """Recompute the operating point from analyst feedback."""

    def __init__(
        self,
        feedback_repo: FeedbackRepository,
        alert_repo: AlertRepository,
        calibration_repo: CalibrationRepository,
        runtime: RuntimeConfig,
    ) -> None:
        self._feedback = feedback_repo
        self._alerts = alert_repo
        self._calibration = calibration_repo
        self._runtime = runtime

    async def execute(self) -> CalibrationSnapshot:
        scores, truths = await self._labeled_scores()
        if not scores:
            raise ValidationError("no definitively-labeled feedback to recalibrate from")

        before = compute_metrics(truths, scores, threshold=self._runtime.threshold)
        after = sweep_threshold(truths, scores, objective="f1")

        # Apply the improved threshold so future detection uses it.
        self._runtime.threshold = after.threshold

        snapshot = CalibrationSnapshot(
            threshold=after.threshold,
            seq_weight=self._runtime.seq_weight,
            stat_weight=self._runtime.stat_weight,
            feedback_count=len(scores),
            precision_before=before.precision,
            recall_before=before.recall,
            precision_after=after.precision,
            recall_after=after.recall,
        )
        return await self._calibration.add(snapshot)

    async def _labeled_scores(self) -> tuple[list[float], list[bool]]:
        # Most recent label per alert wins (all() returns newest first).
        latest: dict[UUID, FeedbackLabel] = {}
        for feedback in await self._feedback.all():
            latest.setdefault(feedback.alert_id, feedback.label)

        scores: list[float] = []
        truths: list[bool] = []
        for alert_id, label in latest.items():
            if label is FeedbackLabel.UNKNOWN:
                continue
            alert = await self._alerts.get(alert_id)
            if alert is None:
                continue
            scores.append(alert.score.value)
            truths.append(label is FeedbackLabel.TRUE_POSITIVE)
        return scores, truths
