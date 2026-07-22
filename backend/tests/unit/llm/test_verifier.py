"""Unit tests for the hallucination verifier — the hard anti-fabrication gate."""

from __future__ import annotations

from nexguard.domain.entities import Alert, IncidentReport, Session
from nexguard.domain.report import (
    EvidenceRef,
    IncidentReportPayload,
    TimelineEntry,
)
from nexguard.domain.value_objects import Severity
from nexguard.domain.verification import EvidenceIndex
from nexguard.infrastructure.llm.prompts import build_report_prompt
from nexguard.infrastructure.llm.stub_provider import StubLLMProvider
from nexguard.infrastructure.llm.verifier import EvidenceVerifier


def _index(session: Session, alert: Alert) -> EvidenceIndex:
    return EvidenceIndex.build(session, alert.evidence)


async def test_grounded_report_passes_verification(
    alert_session: tuple[Session, Alert],
) -> None:
    session, alert = alert_session
    payload = await StubLLMProvider().complete_json(
        build_report_prompt(alert, session), IncidentReportPayload
    )
    report = IncidentReport(alert_id=alert.id, model="stub", payload=payload)

    result = EvidenceVerifier().verify(report, _index(session, alert))

    assert result.is_valid is True
    assert result.reasons == ()
    assert result.checked  # citations were actually checked


def _payload(**overrides: object) -> IncidentReportPayload:
    base: dict[str, object] = {
        "summary": "s",
        "severity": Severity.HIGH,
        "confidence": "high",
        "recommended_investigation_steps": ["look"],
    }
    base.update(overrides)
    return IncidentReportPayload.model_validate(base)


def test_fabricated_host_is_rejected(alert_session: tuple[Session, Alert]) -> None:
    session, alert = alert_session
    report = IncidentReport(
        alert_id=alert.id,
        model="x",
        payload=_payload(evidence_refs=[EvidenceRef(kind="host", ref="9.9.9.9")]),
    )
    result = EvidenceVerifier().verify(report, _index(session, alert))
    assert result.is_valid is False
    assert any("host" in reason for reason in result.reasons)


def test_fabricated_timestamp_is_rejected(alert_session: tuple[Session, Alert]) -> None:
    session, alert = alert_session
    report = IncidentReport(
        alert_id=alert.id,
        model="x",
        payload=_payload(
            timeline=[TimelineEntry(timestamp="1999-01-01T00:00:00+00:00", description="d")]
        ),
    )
    result = EvidenceVerifier().verify(report, _index(session, alert))
    assert result.is_valid is False
    assert any("timestamp" in reason for reason in result.reasons)


def test_fabricated_event_id_is_rejected(alert_session: tuple[Session, Alert]) -> None:
    session, alert = alert_session
    report = IncidentReport(
        alert_id=alert.id,
        model="x",
        payload=_payload(evidence_refs=[EvidenceRef(kind="event", ref="99999")]),
    )
    result = EvidenceVerifier().verify(report, _index(session, alert))
    assert result.is_valid is False
    assert any("event" in reason for reason in result.reasons)


def test_fabricated_component_is_rejected(alert_session: tuple[Session, Alert]) -> None:
    session, alert = alert_session
    report = IncidentReport(
        alert_id=alert.id,
        model="x",
        payload=_payload(affected_components=["blk_totally_made_up"]),
    )
    result = EvidenceVerifier().verify(report, _index(session, alert))
    assert result.is_valid is False
    assert any("component" in reason for reason in result.reasons)


def test_missing_payload_is_rejected(alert_session: tuple[Session, Alert]) -> None:
    _, alert = alert_session
    report = IncidentReport(alert_id=alert.id, model="x", payload=None)
    result = EvidenceVerifier().verify(report, EvidenceIndex(frozenset(), frozenset(), frozenset()))
    assert result.is_valid is False
    assert result.reasons == ("report has no payload",)


def test_real_event_and_host_pass(alert_session: tuple[Session, Alert]) -> None:
    session, alert = alert_session
    report = IncidentReport(
        alert_id=alert.id,
        model="x",
        payload=_payload(
            evidence_refs=[
                EvidenceRef(kind="event", ref="9"),  # in the session
                EvidenceRef(kind="host", ref="10.250.1.10"),  # real src_ip
                EvidenceRef(kind="component", ref="blk_-77"),  # the session id
            ]
        ),
    )
    result = EvidenceVerifier().verify(report, _index(session, alert))
    assert result.is_valid is True
