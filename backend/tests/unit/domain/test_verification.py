"""Unit tests for the EvidenceIndex (the ground-truth for verification)."""

from __future__ import annotations

from datetime import UTC, datetime

from nexguard.domain.entities import LogEvent, Session
from nexguard.domain.evidence import (
    EnsembleEvidence,
    Evidence,
    Provenance,
    SequenceEvidence,
    StatisticalEvidence,
)
from nexguard.domain.value_objects import EventId, Severity
from nexguard.domain.verification import EvidenceIndex


def _evidence(external_id: str, started: str | None = None) -> Evidence:
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
        provenance=Provenance(
            session_external_id=external_id,
            dataset="hdfs",
            event_count=2,
            started_at=started,
        ),
    )


def _session() -> Session:
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    return Session(
        external_id="blk_-42",
        dataset="hdfs",
        events=[
            LogEvent(
                event_id=EventId(5),
                raw="receiving block src: /10.1.2.3",
                line_no=0,
                params={"src_ip": "10.1.2.3"},
                timestamp=ts,
            ),
            LogEvent(event_id=EventId(9), raw="PacketResponder", line_no=1),
        ],
    )


def test_index_knows_real_events_hosts_timestamps() -> None:
    session = _session()
    index = EvidenceIndex.build(
        session, _evidence("blk_-42", "2026-01-01T00:00:00+00:00")
    )

    assert index.has_event(5)
    assert index.has_event("9")
    assert index.has_host("10.1.2.3")  # extracted from a host-like param key
    assert index.has_component("blk_-42")  # the session id itself
    assert index.has_timestamp("2026-01-01T00:00:00+00:00")


def test_index_rejects_fabrications() -> None:
    index = EvidenceIndex.build(_session(), _evidence("blk_-42"))

    assert not index.has_event(999)
    assert not index.has_host("10.9.9.9")  # never appeared in the logs
    assert not index.has_timestamp("1999-12-31T23:59:59+00:00")
    assert not index.has_component("blk_fabricated")
