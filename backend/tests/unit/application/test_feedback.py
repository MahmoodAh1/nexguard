"""Unit tests for the analyst feedback loop + recalibration."""

from __future__ import annotations

from uuid import uuid4

import pytest

from nexguard.application.use_cases.feedback import Recalibrate, SubmitFeedback
from nexguard.config.runtime import RuntimeConfig
from nexguard.config.settings import Settings
from nexguard.domain.entities import Alert, FeedbackLabel
from nexguard.domain.errors import NotFoundError, ValidationError
from nexguard.domain.evidence import (
    EnsembleEvidence,
    Evidence,
    Provenance,
    SequenceEvidence,
    StatisticalEvidence,
)
from nexguard.domain.value_objects import Score, Severity
from nexguard.infrastructure.memory.repositories import (
    InMemoryAlertRepository,
    InMemoryCalibrationRepository,
    InMemoryFeedbackRepository,
)


def _evidence(score: float) -> Evidence:
    return Evidence(
        sequence=SequenceEvidence(anomaly_score=score, confidence=0.8, perplexity=3.0),
        statistical=StatisticalEvidence(anomaly_score=score),
        ensemble=EnsembleEvidence(
            seq_weight=0.6,
            stat_weight=0.4,
            seq_score=score,
            stat_score=score,
            final_score=score,
            threshold=0.5,
            severity=Severity.from_score(score),
        ),
        provenance=Provenance(session_external_id="blk", dataset="hdfs", event_count=3),
    )


def _alert(score: float) -> Alert:
    return Alert(
        session_id=uuid4(),
        score=Score(score),
        severity=Severity.from_score(score),
        evidence=_evidence(score),
    )


def _runtime() -> RuntimeConfig:
    return RuntimeConfig.from_settings(Settings(_env_file=None))  # type: ignore[arg-type]


async def test_submit_feedback_persists_label() -> None:
    alerts = InMemoryAlertRepository()
    feedback_repo = InMemoryFeedbackRepository()
    alert = _alert(0.9)
    await alerts.add(alert)

    analyst = uuid4()
    feedback = await SubmitFeedback(feedback_repo, alerts).execute(
        alert_id=alert.id,
        analyst_id=analyst,
        label=FeedbackLabel.TRUE_POSITIVE,
        note="real",
    )

    assert feedback.label is FeedbackLabel.TRUE_POSITIVE
    assert (await feedback_repo.list_for_alert(alert.id))[0].note == "real"


async def test_submit_feedback_on_missing_alert_raises() -> None:
    with pytest.raises(NotFoundError):
        await SubmitFeedback(InMemoryFeedbackRepository(), InMemoryAlertRepository()).execute(
            alert_id=uuid4(), analyst_id=uuid4(), label=FeedbackLabel.BENIGN
        )


async def test_recalibration_improves_precision_from_feedback() -> None:
    alerts = InMemoryAlertRepository()
    feedback_repo = InMemoryFeedbackRepository()
    calibration = InMemoryCalibrationRepository()
    runtime = _runtime()
    submit = SubmitFeedback(feedback_repo, alerts)

    # 5 true positives at high scores, 3 false positives at low-but-above-threshold.
    for _ in range(5):
        alert = _alert(0.9)
        await alerts.add(alert)
        await submit.execute(
            alert_id=alert.id, analyst_id=uuid4(), label=FeedbackLabel.TRUE_POSITIVE
        )
    for _ in range(3):
        alert = _alert(0.55)
        await alerts.add(alert)
        await submit.execute(
            alert_id=alert.id, analyst_id=uuid4(), label=FeedbackLabel.FALSE_POSITIVE
        )

    snapshot = await Recalibrate(feedback_repo, alerts, calibration, runtime).execute()

    assert snapshot.feedback_count == 8
    assert snapshot.precision_before == pytest.approx(5 / 8)  # 5 TP of 8 alerts
    assert snapshot.precision_after == 1.0  # the FPs are thresholded out
    assert snapshot.precision_after > snapshot.precision_before
    assert snapshot.recall_after == 1.0  # the TPs are kept
    assert runtime.threshold > 0.5  # threshold was raised
    assert (await calibration.latest()) == snapshot


async def test_recalibration_without_feedback_raises() -> None:
    with pytest.raises(ValidationError):
        await Recalibrate(
            InMemoryFeedbackRepository(),
            InMemoryAlertRepository(),
            InMemoryCalibrationRepository(),
            _runtime(),
        ).execute()
