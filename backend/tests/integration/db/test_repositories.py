"""Integration tests for the SQLAlchemy repositories against real SQLite."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from nexguard.domain.entities import (
    Alert,
    AlertStatus,
    IncidentReport,
    LogEvent,
    Session,
    Template,
    User,
    UserRole,
)
from nexguard.domain.evidence import (
    EnsembleEvidence,
    Evidence,
    Provenance,
    SequenceEvidence,
    StatisticalEvidence,
)
from nexguard.domain.report import IncidentReportPayload
from nexguard.domain.value_objects import EventId, Score, Severity
from nexguard.infrastructure.db.repositories import (
    SqlAlchemyAlertRepository,
    SqlAlchemyLogRepository,
    SqlAlchemyReportRepository,
    SqlAlchemyTemplateRepository,
    SqlAlchemyUserRepository,
)
from nexguard.infrastructure.db.session import Database

pytestmark = pytest.mark.integration


def _evidence(external_id: str, severity: Severity) -> Evidence:
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
            severity=severity,
        ),
        provenance=Provenance(
            session_external_id=external_id, dataset="hdfs", event_count=2
        ),
    )


async def test_session_round_trip(database: Database) -> None:
    ts = datetime(2026, 1, 1, tzinfo=UTC)
    session = Session(
        external_id="blk_-1",
        dataset="hdfs",
        label=False,
        events=[
            LogEvent(event_id=EventId(5), raw="r0", line_no=0, timestamp=ts),
            LogEvent(event_id=EventId(9), raw="r1", line_no=1),
        ],
    )
    async with database.session() as s:
        await SqlAlchemyLogRepository(s).add_session(session)

    async with database.session() as s:
        fetched = await SqlAlchemyLogRepository(s).get_session(session.id)

    assert fetched is not None
    assert fetched.external_id == "blk_-1"
    assert fetched.label is False
    assert fetched.event_id_sequence() == [EventId(5), EventId(9)]
    assert fetched.events[0].timestamp == ts

    async with database.session() as s:
        by_ext = await SqlAlchemyLogRepository(s).get_session_by_external_id(
            "hdfs", "blk_-1"
        )
    assert by_ext is not None and by_ext.id == session.id


async def test_alert_add_list_filter_and_update(database: Database) -> None:
    session = Session(external_id="blk_-2", dataset="hdfs")
    async with database.session() as s:
        await SqlAlchemyLogRepository(s).add_session(session)

    critical = Alert(
        session_id=session.id,
        score=Score(0.9),
        severity=Severity.CRITICAL,
        evidence=_evidence("blk_-2", Severity.CRITICAL),
    )
    low = Alert(
        session_id=session.id,
        score=Score(0.2),
        severity=Severity.LOW,
        evidence=_evidence("blk_-2", Severity.LOW),
    )
    async with database.session() as s:
        repo = SqlAlchemyAlertRepository(s)
        await repo.add(critical)
        await repo.add(low)

    async with database.session() as s:
        criticals = await SqlAlchemyAlertRepository(s).list(severity="critical")
    assert [a.id for a in criticals] == [critical.id]
    assert criticals[0].evidence.ensemble.severity is Severity.CRITICAL

    # Update via lifecycle transition.
    critical.transition_to(AlertStatus.TRIAGED)
    async with database.session() as s:
        await SqlAlchemyAlertRepository(s).update(critical)
    async with database.session() as s:
        reloaded = await SqlAlchemyAlertRepository(s).get(critical.id)
    assert reloaded is not None
    assert reloaded.status.value == "triaged"


async def test_user_by_email(database: Database) -> None:
    user = User(email="admin@nexguard.local", password_hash="hash", role=UserRole.ADMIN)
    async with database.session() as s:
        await SqlAlchemyUserRepository(s).add(user)
    async with database.session() as s:
        found = await SqlAlchemyUserRepository(s).by_email("admin@nexguard.local")
    assert found is not None and found.role is UserRole.ADMIN
    async with database.session() as s:
        missing = await SqlAlchemyUserRepository(s).by_email("nobody@nexguard.local")
    assert missing is None


async def test_report_persist_and_fetch_by_alert(database: Database) -> None:
    session = Session(external_id="blk_-3", dataset="hdfs")
    alert = Alert(
        session_id=session.id,
        score=Score(0.9),
        severity=Severity.HIGH,
        evidence=_evidence("blk_-3", Severity.HIGH),
    )
    async with database.session() as s:
        await SqlAlchemyLogRepository(s).add_session(session)
        await SqlAlchemyAlertRepository(s).add(alert)

    payload = IncidentReportPayload(
        summary="s",
        severity=Severity.HIGH,
        confidence="medium",
        recommended_investigation_steps=["look"],
    )
    report = IncidentReport(
        alert_id=alert.id, model="stub", payload=payload, verified=True
    )
    async with database.session() as s:
        await SqlAlchemyReportRepository(s).add(report)

    async with database.session() as s:
        fetched = await SqlAlchemyReportRepository(s).get_by_alert(alert.id)
    assert fetched is not None
    assert fetched.verified is True
    assert fetched.payload is not None and fetched.payload.summary == "s"


async def test_template_upsert_is_idempotent(database: Database) -> None:
    repo_templates = [
        Template(event_id=EventId(1), template="a", occurrences=3),
        Template(event_id=EventId(2), template="b", occurrences=1),
    ]
    async with database.session() as s:
        await SqlAlchemyTemplateRepository(s).upsert_many(repo_templates)

    # Upsert again with an updated occurrence count for event 1.
    async with database.session() as s:
        await SqlAlchemyTemplateRepository(s).upsert_many(
            [Template(event_id=EventId(1), template="a", occurrences=10)]
        )
    async with database.session() as s:
        all_templates = await SqlAlchemyTemplateRepository(s).all()

    assert len(all_templates) == 2  # no duplicate for event 1
    by_id = {int(t.event_id): t for t in all_templates}
    assert by_id[1].occurrences == 10
