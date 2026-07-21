"""Unit tests for the DetectAnomalies use case (fakes for detectors)."""

from __future__ import annotations

from collections.abc import Sequence

from nexguard.application.use_cases.detect_anomalies import DetectAnomalies
from nexguard.domain.detection import SequenceVerdict, StatisticalVerdict
from nexguard.domain.entities import LogEvent, Session
from nexguard.domain.events import AlertCreated
from nexguard.domain.value_objects import CountVector, EventId
from nexguard.infrastructure.bus.memory_bus import InMemoryEventBus
from nexguard.infrastructure.detection.ensemble import WeightedEnsemble
from nexguard.infrastructure.detection.explain import Explainer
from nexguard.infrastructure.memory.repositories import InMemoryAlertRepository


class _FixedSequenceDetector:
    def __init__(self, score: float) -> None:
        self._score = score

    def score(self, sequence: Sequence[EventId]) -> SequenceVerdict:
        return SequenceVerdict(
            anomaly_score=self._score,
            confidence=0.8,
            perplexity=5.0,
            actual_event=EventId(9),
            predicted_topk=(EventId(3),),
            surprising_step_indices=(1,),
            suspicious_subsequence=(EventId(5), EventId(9)),
        )


class _FixedStatisticalDetector:
    def __init__(self, score: float) -> None:
        self._score = score

    def score(self, counts: CountVector) -> StatisticalVerdict:
        return StatisticalVerdict(anomaly_score=self._score)


def _session() -> Session:
    return Session(
        external_id="blk_-9",
        dataset="hdfs",
        events=[LogEvent(event_id=EventId(5), raw="r", line_no=0)],
    )


def _use_case(
    seq_score: float, stat_score: float
) -> tuple[DetectAnomalies, InMemoryAlertRepository, InMemoryEventBus]:
    alerts = InMemoryAlertRepository()
    bus = InMemoryEventBus()
    use_case = DetectAnomalies(
        sequence_detector=_FixedSequenceDetector(seq_score),
        statistical_detector=_FixedStatisticalDetector(stat_score),
        ensemble=WeightedEnsemble(seq_weight=0.6, stat_weight=0.4, threshold=0.5),
        explainer=Explainer(),
        alert_repo=alerts,
        event_bus=bus,
    )
    return use_case, alerts, bus


async def test_anomalous_session_creates_alert_and_publishes_event() -> None:
    use_case, alerts, bus = _use_case(seq_score=0.9, stat_score=0.8)
    session = _session()

    alert = await use_case.execute(session)

    assert alert is not None
    assert alert.session_id == session.id
    assert alert.evidence.sequence.suspicious_subsequence == [EventId(5), EventId(9)]
    assert await alerts.get(alert.id) is not None
    assert len(bus.published) == 1
    event = bus.published[0]
    assert isinstance(event, AlertCreated)
    assert event.alert_id == alert.id
    assert event.session_external_id == "blk_-9"


async def test_normal_session_creates_no_alert() -> None:
    use_case, alerts, bus = _use_case(seq_score=0.1, stat_score=0.1)

    alert = await use_case.execute(_session())

    assert alert is None
    assert await alerts.list() == []
    assert bus.published == []
