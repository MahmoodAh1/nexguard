"""Shared pytest fixtures.

The `src` layout is on the path via `[tool.pytest.ini_options].pythonpath`, so
tests import `nexguard.*` directly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nexguard.domain.entities import Alert, LogEvent, Session
from nexguard.domain.evidence import (
    EnsembleEvidence,
    Evidence,
    FeatureContribution,
    Provenance,
    SequenceEvidence,
    StatisticalEvidence,
)
from nexguard.domain.value_objects import EventId, Score, Severity


def build_session_and_alert(
    *, with_timestamps: bool = True, with_hosts: bool = True
) -> tuple[Session, Alert]:
    """A consistent session + alert whose evidence references only real facts."""
    base = datetime(2008, 11, 9, 20, 0, 0, tzinfo=UTC)
    sequence = [1, 2, 3, 4, 9]
    events = [
        LogEvent(
            event_id=EventId(eid),
            raw=f"081109 20000{i} INFO event {eid}",
            line_no=i,
            params={"src_ip": f"10.250.1.{10 + i}"} if with_hosts else {},
            timestamp=base + timedelta(seconds=i) if with_timestamps else None,
        )
        for i, eid in enumerate(sequence)
    ]
    session = Session(external_id="blk_-77", dataset="hdfs", events=events, label=True)
    time_range = session.time_range
    evidence = Evidence(
        sequence=SequenceEvidence(
            anomaly_score=0.8,
            confidence=0.7,
            perplexity=6.0,
            actual_event=EventId(9),
            predicted_topk=[EventId(4)],
            surprising_step_indices=[4],
            suspicious_subsequence=[EventId(3), EventId(9)],
        ),
        statistical=StatisticalEvidence(
            anomaly_score=0.6,
            important_features=[
                FeatureContribution(
                    event_id=EventId(2), template="ReceivingBlock", contribution=0.3
                )
            ],
        ),
        ensemble=EnsembleEvidence(
            seq_weight=0.6,
            stat_weight=0.4,
            seq_score=0.8,
            stat_score=0.6,
            final_score=0.72,
            threshold=0.5,
            severity=Severity.HIGH,
        ),
        provenance=Provenance(
            session_external_id="blk_-77",
            dataset="hdfs",
            event_count=len(sequence),
            started_at=time_range.start.isoformat() if time_range else None,
            ended_at=time_range.end.isoformat() if time_range else None,
        ),
    )
    alert = Alert(
        session_id=session.id,
        score=Score(0.72),
        severity=Severity.HIGH,
        evidence=evidence,
    )
    return session, alert


@pytest.fixture
def alert_session() -> tuple[Session, Alert]:
    return build_session_and_alert()
