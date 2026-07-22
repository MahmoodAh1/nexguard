"""Unit tests for domain entities and their behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from nexguard.domain.entities import (
    Alert,
    AlertStatus,
    LogEvent,
    Session,
    UserRole,
)
from nexguard.domain.errors import ValidationError
from nexguard.domain.evidence import (
    EnsembleEvidence,
    Evidence,
    Provenance,
    SequenceEvidence,
    StatisticalEvidence,
)
from nexguard.domain.value_objects import EventId, Score, Severity


def _event(event_id: int, line_no: int, ts: datetime | None = None) -> LogEvent:
    return LogEvent(
        event_id=EventId(event_id), raw=f"line-{line_no}", line_no=line_no, timestamp=ts
    )


def _evidence() -> Evidence:
    return Evidence(
        sequence=SequenceEvidence(anomaly_score=0.9, confidence=0.8, perplexity=3.0),
        statistical=StatisticalEvidence(anomaly_score=0.7),
        ensemble=EnsembleEvidence(
            seq_weight=0.6,
            stat_weight=0.4,
            seq_score=0.9,
            stat_score=0.7,
            final_score=0.82,
            threshold=0.5,
            severity=Severity.CRITICAL,
        ),
        provenance=Provenance(session_external_id="blk_1", dataset="hdfs", event_count=3),
    )


class TestSession:
    def test_sequence_and_counts(self) -> None:
        session = Session(
            external_id="blk_1",
            dataset="hdfs",
            events=[_event(5, 0), _event(9, 1), _event(5, 2)],
        )
        assert session.event_id_sequence() == [EventId(5), EventId(9), EventId(5)]
        assert session.event_counts() == {EventId(5): 2, EventId(9): 1}
        assert session.unique_event_ids() == {EventId(5), EventId(9)}
        assert session.event_count == 3

    def test_time_range_spans_events(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        session = Session(
            external_id="blk_1",
            dataset="hdfs",
            events=[_event(1, 0, base + timedelta(seconds=2)), _event(2, 1, base)],
        )
        rng = session.time_range
        assert rng is not None
        assert rng.start == base
        assert rng.end == base + timedelta(seconds=2)

    def test_time_range_none_when_no_timestamps(self) -> None:
        session = Session(external_id="blk_1", dataset="hdfs", events=[_event(1, 0)])
        assert session.time_range is None


class TestAlertLifecycle:
    def _alert(self, status: AlertStatus) -> Alert:
        alert = Alert(
            session_id=uuid4(),
            score=Score(0.82),
            severity=Severity.CRITICAL,
            evidence=_evidence(),
        )
        alert.status = status
        return alert

    def test_legal_transition(self) -> None:
        alert = self._alert(AlertStatus.NEW)
        alert.transition_to(AlertStatus.TRIAGED)
        assert alert.status.value == "triaged"
        alert.transition_to(AlertStatus.INVESTIGATING)
        assert alert.status.value == "investigating"

    def test_illegal_transition_rejected(self) -> None:
        alert = self._alert(AlertStatus.NEW)
        with pytest.raises(ValidationError):
            alert.transition_to(AlertStatus.RESOLVED)

    def test_terminal_status_cannot_move(self) -> None:
        alert = self._alert(AlertStatus.RESOLVED)
        with pytest.raises(ValidationError):
            alert.transition_to(AlertStatus.INVESTIGATING)


class TestUserRole:
    def test_hierarchy(self) -> None:
        assert UserRole.ADMIN.satisfies(UserRole.VIEWER)
        assert UserRole.ADMIN.satisfies(UserRole.ADMIN)
        assert UserRole.ANALYST.satisfies(UserRole.VIEWER)
        assert not UserRole.VIEWER.satisfies(UserRole.ANALYST)
        assert not UserRole.ANALYST.satisfies(UserRole.ADMIN)
