"""Deterministic stub LLM provider.

Implements the :class:`~nexguard.domain.ports.LLMProvider` port without any model,
so the full triage pipeline runs (and is tested) anywhere — including CI where
Ollama is absent. It simulates a well-behaved model: it reads the grounding block
from the prompt and emits a schema-valid report that references only real facts,
so verification passes. It never fabricates.
"""

from __future__ import annotations

from typing import TypeVar, cast

from pydantic import BaseModel

from nexguard.domain.report import (
    EvidenceRef,
    IncidentReportPayload,
    MitreHypothesis,
    ReportConfidence,
    TimelineEntry,
)
from nexguard.domain.value_objects import EventId, Severity
from nexguard.infrastructure.llm.prompts import extract_grounding

TModel = TypeVar("TModel", bound=BaseModel)

_CONFIDENCE_BY_SEVERITY: dict[Severity, ReportConfidence] = {
    Severity.LOW: "low",
    Severity.MEDIUM: "medium",
    Severity.HIGH: "high",
    Severity.CRITICAL: "high",
}


class StubLLMProvider:
    """A grounded, deterministic report generator for dev/CI."""

    name = "stub"

    async def complete_json(self, prompt: str, schema: type[TModel]) -> TModel:
        if schema is not IncidentReportPayload:
            raise NotImplementedError(
                f"StubLLMProvider only synthesizes {IncidentReportPayload.__name__}, "
                f"not {schema.__name__}"
            )
        return cast(TModel, self._report(extract_grounding(prompt)))

    def _report(self, g: dict[str, object]) -> IncidentReportPayload:
        severity = Severity(str(g["severity"]))
        session_id = str(g["session_external_id"])
        dataset = str(g["dataset"])
        hosts = _as_str_list(g.get("hosts"))
        timestamps = _as_str_list(g.get("timestamps"))
        suspicious = _as_int_list(g.get("suspicious_subsequence"))
        event_ids = _as_int_list(g.get("event_ids"))
        raw_actual = g.get("actual_event")
        actual_event = raw_actual if isinstance(raw_actual, int) else None
        cited_events = suspicious or event_ids[:3]

        return IncidentReportPayload(
            summary=(
                f"Anomalous {dataset.upper()} block lifecycle detected for session "
                f"{session_id} (severity: {severity.value}). The sequence model was "
                f"repeatedly surprised and the statistical model found an unusual "
                f"event composition."
            ),
            severity=severity,
            confidence=_CONFIDENCE_BY_SEVERITY[severity],
            timeline=self._timeline(timestamps, cited_events, actual_event),
            affected_components=[session_id, *hosts],
            evidence_refs=self._evidence_refs(
                cited_events, hosts, timestamps, session_id
            ),
            mitre_hypotheses=self._mitre(severity),
            recommended_investigation_steps=[
                f"Review the full event sequence for block {session_id} and compare "
                f"against a known-good block lifecycle.",
                "Correlate the flagged datanodes with host-level metrics and logs "
                "around the anomaly window.",
                "Confirm whether the surprising event order reflects a genuine fault "
                "(disk/network) or benign operational variance.",
            ],
            recommended_containment_actions=[
                "If corruption is suspected, quarantine the affected block replicas "
                "and trigger re-replication from a healthy source.",
                "Increase monitoring on the implicated datanodes pending triage.",
            ],
        )

    @staticmethod
    def _timeline(
        timestamps: list[str], cited_events: list[int], actual_event: int | None
    ) -> list[TimelineEntry]:
        if not timestamps:
            return []
        entries = [
            TimelineEntry(
                timestamp=timestamps[0],
                description="Session activity began; block lifecycle initiated.",
                event_id=EventId(cited_events[0]) if cited_events else None,
            )
        ]
        if len(timestamps) > 1:
            entries.append(
                TimelineEntry(
                    timestamp=timestamps[-1],
                    description="Anomalous deviation from the expected event order observed.",
                    event_id=(
                        EventId(actual_event) if actual_event is not None else None
                    ),
                )
            )
        return entries

    @staticmethod
    def _evidence_refs(
        cited_events: list[int],
        hosts: list[str],
        timestamps: list[str],
        session_id: str,
    ) -> list[EvidenceRef]:
        refs: list[EvidenceRef] = [EvidenceRef(kind="component", ref=session_id)]
        refs += [EvidenceRef(kind="event", ref=str(e)) for e in cited_events[:5]]
        refs += [EvidenceRef(kind="host", ref=h) for h in hosts[:3]]
        refs += [EvidenceRef(kind="timestamp", ref=t) for t in timestamps[:1]]
        return refs

    @staticmethod
    def _mitre(severity: Severity) -> list[MitreHypothesis]:
        hypotheses = [
            MitreHypothesis(
                technique_id="T1499",
                name="Endpoint Denial of Service",
                rationale=(
                    "An abnormal block write/response sequence can indicate resource "
                    "exhaustion or a datanode under stress."
                ),
                confidence="low",
            ),
            MitreHypothesis(
                technique_id="T1565.001",
                name="Stored Data Manipulation",
                rationale=(
                    "Deviation in the storage lifecycle could reflect tampering with "
                    "stored block data; requires corroboration."
                ),
                confidence="low",
            ),
        ]
        return hypotheses if severity.rank >= Severity.HIGH.rank else hypotheses[:1]


def _as_str_list(value: object) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else []


def _as_int_list(value: object) -> list[int]:
    return [int(v) for v in value] if isinstance(value, list) else []
