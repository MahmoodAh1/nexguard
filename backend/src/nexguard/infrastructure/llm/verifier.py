"""Hallucination verification.

Implements the :class:`~nexguard.domain.ports.ReportVerifier` port. It is a HARD
gate: every citation a report makes — evidence refs, timeline event ids and
timestamps, and affected components — must resolve against the
:class:`EvidenceIndex` built from the real, persisted session and its evidence.
Any unresolved reference means the report referenced something that does not
exist, and the report is rejected. MITRE techniques are hypotheses by schema, so
they are not treated as citations to verify.
"""

from __future__ import annotations

from nexguard.domain.entities import IncidentReport
from nexguard.domain.report import CitationKind
from nexguard.domain.verification import Citation, EvidenceIndex, VerificationResult


class EvidenceVerifier:
    """Rejects any report that cites evidence absent from the index."""

    def verify(self, report: IncidentReport, evidence_index: EvidenceIndex) -> VerificationResult:
        payload = report.payload
        if payload is None:
            return VerificationResult(is_valid=False, reasons=("report has no payload",))

        reasons: list[str] = []
        checked: list[Citation] = []

        for ref in payload.evidence_refs:
            citation = Citation(kind=ref.kind, ref=ref.ref)
            checked.append(citation)
            if not self._resolves(ref.kind, ref.ref, evidence_index):
                reasons.append(f"unverifiable {ref.kind} citation: {ref.ref!r}")

        for index, entry in enumerate(payload.timeline):
            checked.append(Citation(kind="timestamp", ref=entry.timestamp))
            if not evidence_index.has_timestamp(entry.timestamp):
                reasons.append(f"timeline[{index}] cites unknown timestamp: {entry.timestamp!r}")
            if entry.event_id is not None and not evidence_index.has_event(int(entry.event_id)):
                reasons.append(f"timeline[{index}] cites unknown event id: {int(entry.event_id)}")

        for component in payload.affected_components:
            checked.append(Citation(kind="component", ref=component))
            if not evidence_index.has_component(component):
                reasons.append(f"unverifiable affected component: {component!r}")

        return VerificationResult(
            is_valid=not reasons, reasons=tuple(reasons), checked=tuple(checked)
        )

    @staticmethod
    def _resolves(kind: CitationKind, ref: str, index: EvidenceIndex) -> bool:
        if kind == "event":
            return index.has_event(ref)
        if kind == "timestamp":
            return index.has_timestamp(ref)
        if kind == "host":
            return index.has_host(ref)
        return index.has_component(ref)
