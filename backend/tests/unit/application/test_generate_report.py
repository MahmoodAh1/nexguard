"""Unit tests for the GenerateReport use case."""

from __future__ import annotations

from typing import TypeVar
from uuid import uuid4

import pytest
from pydantic import BaseModel

from nexguard.application.use_cases.generate_report import GenerateReport
from nexguard.domain.entities import Alert, Session
from nexguard.domain.errors import NotFoundError
from nexguard.domain.events import ReportGenerated
from nexguard.infrastructure.bus.memory_bus import InMemoryEventBus
from nexguard.infrastructure.llm.stub_provider import StubLLMProvider
from nexguard.infrastructure.llm.verifier import EvidenceVerifier
from nexguard.infrastructure.memory.repositories import (
    InMemoryAlertRepository,
    InMemoryLogRepository,
    InMemoryReportRepository,
)

_TModel = TypeVar("_TModel", bound=BaseModel)


class _FabricatingLLM:
    """A hostile model that cites a host which never appears in the logs."""

    async def complete_json(self, prompt: str, schema: type[_TModel]) -> _TModel:
        return schema.model_validate(
            {
                "summary": "fabricated",
                "severity": "high",
                "confidence": "high",
                "evidence_refs": [{"kind": "host", "ref": "6.6.6.6"}],
                "recommended_investigation_steps": ["x"],
            }
        )


async def _wire(
    session: Session, alert: Alert
) -> tuple[
    InMemoryAlertRepository,
    InMemoryReportRepository,
    InMemoryLogRepository,
    InMemoryEventBus,
]:
    logs = InMemoryLogRepository()
    alerts = InMemoryAlertRepository()
    reports = InMemoryReportRepository()
    bus = InMemoryEventBus()
    await logs.add_session(session)
    await alerts.add(alert)
    return alerts, reports, logs, bus


async def test_grounded_report_is_verified_persisted_and_published(
    alert_session: tuple[Session, Alert],
) -> None:
    session, alert = alert_session
    alerts, reports, logs, bus = await _wire(session, alert)
    use_case = GenerateReport(
        llm=StubLLMProvider(),
        verifier=EvidenceVerifier(),
        alert_repo=alerts,
        report_repo=reports,
        log_repo=logs,
        model_name="stub",
        event_bus=bus,
    )

    report = await use_case.execute(alert.id)

    assert report.verified is True
    assert report.rejected_reasons == []
    assert report.payload is not None
    assert await reports.get_by_alert(alert.id) is not None
    assert len(bus.published) == 1
    event = bus.published[0]
    assert isinstance(event, ReportGenerated)
    assert event.verified is True


async def test_report_is_cached_and_not_regenerated(
    alert_session: tuple[Session, Alert],
) -> None:
    session, alert = alert_session
    alerts, reports, logs, bus = await _wire(session, alert)
    use_case = GenerateReport(
        llm=StubLLMProvider(),
        verifier=EvidenceVerifier(),
        alert_repo=alerts,
        report_repo=reports,
        log_repo=logs,
        model_name="stub",
        event_bus=bus,
    )

    first = await use_case.execute(alert.id)
    second = await use_case.execute(alert.id)

    assert first.id == second.id
    assert len(bus.published) == 1  # second call served from cache, no re-publish


async def test_fabricating_model_yields_rejected_report(
    alert_session: tuple[Session, Alert],
) -> None:
    session, alert = alert_session
    alerts, reports, logs, bus = await _wire(session, alert)
    use_case = GenerateReport(
        llm=_FabricatingLLM(),
        verifier=EvidenceVerifier(),
        alert_repo=alerts,
        report_repo=reports,
        log_repo=logs,
        model_name="hostile",
        event_bus=bus,
    )

    report = await use_case.execute(alert.id)

    assert report.verified is False
    assert report.rejected_reasons  # explains why it was rejected
    assert any("6.6.6.6" in reason for reason in report.rejected_reasons)
    # Rejected reports are still persisted for audit, and the rejection is published.
    assert await reports.get_by_alert(alert.id) is not None
    event = bus.published[0]
    assert isinstance(event, ReportGenerated)
    assert event.verified is False


async def test_missing_alert_raises_not_found(
    alert_session: tuple[Session, Alert],
) -> None:
    session, alert = alert_session
    alerts, reports, logs, _ = await _wire(session, alert)
    use_case = GenerateReport(
        llm=StubLLMProvider(),
        verifier=EvidenceVerifier(),
        alert_repo=alerts,
        report_repo=reports,
        log_repo=logs,
        model_name="stub",
    )

    with pytest.raises(NotFoundError):
        await use_case.execute(uuid4())
