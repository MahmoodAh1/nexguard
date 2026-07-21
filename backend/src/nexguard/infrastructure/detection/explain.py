"""Explainability assembly.

Turns the raw detector verdicts into the domain :class:`Evidence` object — the
single source of truth attached to every alert and the only thing the LLM triage
copilot and the verifier are allowed to reference.
"""

from __future__ import annotations

from nexguard.domain.detection import (
    EnsembleVerdict,
    SequenceVerdict,
    StatisticalVerdict,
)
from nexguard.domain.entities import Session
from nexguard.domain.evidence import (
    EnsembleEvidence,
    Evidence,
    Provenance,
    SequenceEvidence,
    StatisticalEvidence,
)


class Explainer:
    """Assembles the structured Evidence for an alert."""

    def build(
        self,
        session: Session,
        sequence: SequenceVerdict,
        statistical: StatisticalVerdict,
        ensemble: EnsembleVerdict,
    ) -> Evidence:
        time_range = session.time_range
        return Evidence(
            sequence=SequenceEvidence(
                anomaly_score=sequence.anomaly_score,
                confidence=sequence.confidence,
                perplexity=sequence.perplexity,
                actual_event=sequence.actual_event,
                predicted_topk=list(sequence.predicted_topk),
                surprising_step_indices=list(sequence.surprising_step_indices),
                suspicious_subsequence=list(sequence.suspicious_subsequence),
            ),
            statistical=StatisticalEvidence(
                anomaly_score=statistical.anomaly_score,
                important_features=list(statistical.important_features),
            ),
            ensemble=EnsembleEvidence(
                seq_weight=ensemble.seq_weight,
                stat_weight=ensemble.stat_weight,
                seq_score=ensemble.seq_score,
                stat_score=ensemble.stat_score,
                final_score=ensemble.final_score.value,
                threshold=ensemble.threshold,
                severity=ensemble.severity,
            ),
            provenance=Provenance(
                session_external_id=session.external_id,
                dataset=session.dataset,
                event_count=session.event_count,
                started_at=time_range.start.isoformat() if time_range else None,
                ended_at=time_range.end.isoformat() if time_range else None,
            ),
        )
