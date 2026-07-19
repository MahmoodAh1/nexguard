"""Hallucination verification types.

The :class:`EvidenceIndex` is the set of facts that provably exist for an alert —
built from the real, persisted session and its evidence. The verifier checks a
generated report's every citation against this index; anything not found is a
fabrication and causes rejection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from nexguard.domain.entities import Session
from nexguard.domain.evidence import Evidence

# Param keys whose values we treat as host/component identifiers worth verifying.
_HOSTLIKE_KEYS = re.compile(
    r"(host|node|ip|addr|src|dst|component|service)", re.IGNORECASE
)


@dataclass(frozen=True, slots=True)
class Citation:
    """A single claim a report makes that must be grounded in evidence."""

    kind: str  # event | host | timestamp | component
    ref: str


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Outcome of verifying a report against an :class:`EvidenceIndex`."""

    is_valid: bool
    reasons: tuple[str, ...] = ()
    checked: tuple[Citation, ...] = ()


@dataclass(frozen=True, slots=True)
class EvidenceIndex:
    """The provable facts for an alert. Everything a report may cite must be here."""

    event_ids: frozenset[int]
    timestamps: frozenset[str]
    tokens: frozenset[str]  # host/component identifiers seen in the raw evidence

    def has_event(self, ref: str | int) -> bool:
        try:
            return int(ref) in self.event_ids
        except (TypeError, ValueError):
            return False

    def has_timestamp(self, ref: str) -> bool:
        return ref in self.timestamps

    def has_host(self, ref: str) -> bool:
        return ref in self.tokens

    def has_component(self, ref: str) -> bool:
        return ref in self.tokens

    @classmethod
    def build(cls, session: Session, evidence: Evidence) -> EvidenceIndex:
        event_ids: set[int] = {int(e) for e in session.unique_event_ids()}
        event_ids.update(int(e) for e in evidence.sequence.suspicious_subsequence)

        timestamps: set[str] = {
            e.timestamp.isoformat() for e in session.events if e.timestamp is not None
        }
        for maybe_ts in (evidence.provenance.started_at, evidence.provenance.ended_at):
            if maybe_ts:
                timestamps.add(maybe_ts)

        tokens: set[str] = {session.external_id, session.dataset}
        for event in session.events:
            for key, value in event.params.items():
                if _HOSTLIKE_KEYS.search(key):
                    tokens.add(value)

        return cls(
            event_ids=frozenset(event_ids),
            timestamps=frozenset(timestamps),
            tokens=frozenset(tokens),
        )
