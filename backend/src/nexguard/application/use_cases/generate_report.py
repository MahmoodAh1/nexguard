"""Generate-report use case.

For a suspicious alert: fetch its session, prompt the local LLM for a structured
incident report, then run the report through the hallucination verifier. Verified
reports are persisted as accepted; rejected reports are persisted too — with the
reasons — so a rejection is auditable and observable, never silent. Either way a
``ReportGenerated`` event is published for live consumers.
"""

from __future__ import annotations

from uuid import UUID

from nexguard.domain.entities import IncidentReport
from nexguard.domain.errors import NotFoundError
from nexguard.domain.events import ReportGenerated
from nexguard.domain.ports import (
    AlertRepository,
    EventBus,
    LLMProvider,
    LogRepository,
    ReportRepository,
    ReportVerifier,
)
from nexguard.domain.report import IncidentReportPayload
from nexguard.domain.verification import EvidenceIndex
from nexguard.infrastructure.llm.prompts import build_report_prompt


class GenerateReport:
    """Draft and verify an incident report for an alert."""

    def __init__(
        self,
        *,
        llm: LLMProvider,
        verifier: ReportVerifier,
        alert_repo: AlertRepository,
        report_repo: ReportRepository,
        log_repo: LogRepository,
        model_name: str,
        event_bus: EventBus | None = None,
    ) -> None:
        self._llm = llm
        self._verifier = verifier
        self._alerts = alert_repo
        self._reports = report_repo
        self._logs = log_repo
        self._model_name = model_name
        self._bus = event_bus

    async def execute(
        self, alert_id: UUID, *, regenerate: bool = False
    ) -> IncidentReport:
        if not regenerate:
            existing = await self._reports.get_by_alert(alert_id)
            if existing is not None:
                return existing

        alert = await self._alerts.get(alert_id)
        if alert is None:
            raise NotFoundError("Alert", alert_id)
        session = await self._logs.get_session(alert.session_id)
        if session is None:
            raise NotFoundError("Session", alert.session_id)

        prompt = build_report_prompt(alert, session)
        payload = await self._llm.complete_json(prompt, IncidentReportPayload)

        report = IncidentReport(
            alert_id=alert.id, model=self._model_name, payload=payload
        )
        result = self._verifier.verify(
            report, EvidenceIndex.build(session, alert.evidence)
        )
        report.verified = result.is_valid
        report.rejected_reasons = list(result.reasons)

        await self._reports.add(report)
        if self._bus is not None:
            await self._bus.publish(
                ReportGenerated(
                    alert_id=alert.id, report_id=report.id, verified=report.verified
                )
            )
        return report
