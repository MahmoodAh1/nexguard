"""Unit tests for the deterministic stub LLM provider."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from nexguard.domain.entities import Alert, Session
from nexguard.domain.report import IncidentReportPayload
from nexguard.domain.value_objects import Severity
from nexguard.infrastructure.llm.prompts import build_report_prompt
from nexguard.infrastructure.llm.stub_provider import StubLLMProvider


async def test_stub_emits_grounded_valid_report(
    alert_session: tuple[Session, Alert],
) -> None:
    session, alert = alert_session
    prompt = build_report_prompt(alert, session)

    payload = await StubLLMProvider().complete_json(prompt, IncidentReportPayload)

    assert payload.severity is Severity.HIGH
    assert payload.confidence == "high"
    assert session.external_id in payload.affected_components
    assert "10.250.1.10" in payload.affected_components  # a real host token
    assert payload.evidence_refs  # non-empty
    assert payload.recommended_investigation_steps
    # Every MITRE technique is a hypothesis.
    assert all(h.is_hypothesis is True for h in payload.mitre_hypotheses)


async def test_stub_rejects_unknown_schema(
    alert_session: tuple[Session, Alert],
) -> None:
    session, alert = alert_session

    class Other(BaseModel):
        value: int

    with pytest.raises(NotImplementedError):
        await StubLLMProvider().complete_json(
            build_report_prompt(alert, session), Other
        )
