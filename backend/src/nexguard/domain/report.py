"""The incident report schema — the LLM triage copilot's output contract.

This is a strict Pydantic v2 schema. The LLM is prompted to emit JSON matching it
(Ollama ``format=json``), and the output is validated before it can touch
application logic — never regex-parsed free text.

Safety property: MITRE ATT&CK techniques are structurally constrained to be
**hypotheses**. There is no field to assert a technique as confirmed fact; the
``is_hypothesis`` flag is ``Literal[True]``, so a model that tries to present a
technique as confirmed fails validation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from nexguard.domain.value_objects import EventId, Severity

ReportConfidence = Literal["low", "medium", "high"]
CitationKind = Literal["event", "host", "timestamp", "component"]


class _ReportModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MitreHypothesis(_ReportModel):
    """A *hypothesized* MITRE ATT&CK technique — never a confirmed fact."""

    technique_id: str = Field(pattern=r"^T\d{4}(\.\d{3})?$")
    name: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    confidence: ReportConfidence
    # Structurally pinned: a technique can only ever be a hypothesis.
    is_hypothesis: Literal[True] = True


class TimelineEntry(_ReportModel):
    """A single step in the incident timeline.

    ``timestamp`` and ``event_id`` (when present) are verified against real
    evidence; a fabricated timestamp causes the whole report to be rejected.
    """

    timestamp: str = Field(min_length=1)
    description: str = Field(min_length=1)
    event_id: EventId | None = None


class EvidenceRef(_ReportModel):
    """A citation the report makes. Every ref is checked by the verifier."""

    kind: CitationKind
    ref: str = Field(min_length=1)


class IncidentReportPayload(_ReportModel):
    """The structured, analyst-ready incident report."""

    summary: str = Field(min_length=1)
    severity: Severity
    confidence: ReportConfidence
    timeline: list[TimelineEntry] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    mitre_hypotheses: list[MitreHypothesis] = Field(default_factory=list)
    recommended_investigation_steps: list[str] = Field(min_length=1)
    recommended_containment_actions: list[str] = Field(default_factory=list)

    @staticmethod
    def json_schema_str() -> str:
        """A compact JSON-schema description for embedding in the LLM prompt."""
        import json

        return json.dumps(IncidentReportPayload.model_json_schema(), indent=2)
