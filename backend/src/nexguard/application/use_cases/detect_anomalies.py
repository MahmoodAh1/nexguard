"""Detect-anomalies use case.

Runs a session through both detectors and the ensemble, assembles explainable
evidence, and — when the ensemble decides an alert — persists it and publishes an
``AlertCreated`` event for live consumers. Depends only on ports, so the same use
case serves the API, the streaming worker, and the seed pipeline.
"""

from __future__ import annotations

import time

from nexguard.domain.entities import Alert, Session
from nexguard.domain.events import AlertCreated
from nexguard.domain.ports import (
    AlertRepository,
    Ensemble,
    EventBus,
    SequenceDetector,
    StatisticalDetector,
)
from nexguard.domain.value_objects import CountVector
from nexguard.infrastructure.detection.explain import Explainer


class DetectAnomalies:
    """Score a session and raise an explainable alert when warranted."""

    def __init__(
        self,
        *,
        sequence_detector: SequenceDetector,
        statistical_detector: StatisticalDetector,
        ensemble: Ensemble,
        explainer: Explainer,
        alert_repo: AlertRepository,
        event_bus: EventBus,
    ) -> None:
        self._sequence = sequence_detector
        self._statistical = statistical_detector
        self._ensemble = ensemble
        self._explainer = explainer
        self._alerts = alert_repo
        self._bus = event_bus

    async def execute(self, session: Session) -> Alert | None:
        started = time.perf_counter()

        sequence_verdict = self._sequence.score(session.event_id_sequence())
        statistical_verdict = self._statistical.score(self._count_vector(session))
        ensemble_verdict = self._ensemble.combine(sequence_verdict, statistical_verdict)
        evidence = self._explainer.build(
            session, sequence_verdict, statistical_verdict, ensemble_verdict
        )

        if not ensemble_verdict.is_alert:
            return None

        alert = Alert(
            session_id=session.id,
            score=ensemble_verdict.final_score,
            severity=ensemble_verdict.severity,
            evidence=evidence,
        )
        await self._alerts.add(alert)
        await self._bus.publish(
            AlertCreated(
                alert_id=alert.id,
                session_external_id=session.external_id,
                severity=alert.severity,
                score=alert.score.value,
            )
        )
        _ = time.perf_counter() - started  # latency available for observability hooks
        return alert

    @staticmethod
    def _count_vector(session: Session) -> CountVector:
        counts = session.event_counts()
        return CountVector.from_counts(counts, tuple(counts.keys()))
