"""The explainability contract.

Every :class:`~nexguard.domain.entities.Alert` carries an :class:`Evidence`
object assembled from both detectors and the ensemble. It is the **single source
of truth** for an alert: the LLM triage copilot may only reference what appears
here, and the verifier checks generated reports against it. Anything an LLM cites
that is absent from this structure is treated as a fabrication.

These are structured value objects. We model them with frozen Pydantic v2 models
(rather than dataclasses) because they must serialize losslessly to JSON — both
for persistence (stored on the ``alerts`` row) and for the API — and value
equality is the correct semantics for them.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from nexguard.domain.value_objects import EventId, Severity


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FeatureContribution(_Frozen):
    """How much a single template's count drove the statistical anomaly score."""

    event_id: EventId
    template: str | None = None
    contribution: float


class SequenceEvidence(_Frozen):
    """Evidence from the DeepLog-style next-event-prediction model."""

    anomaly_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    perplexity: float = Field(ge=0.0)
    # The step where prediction most strongly failed (for the headline evidence).
    actual_event: EventId | None = None
    predicted_topk: list[EventId] = Field(default_factory=list)
    # Every step index (into the session sequence) the model found surprising.
    surprising_step_indices: list[int] = Field(default_factory=list)
    # The contiguous window(s) of events around the failures — the "smoking gun".
    suspicious_subsequence: list[EventId] = Field(default_factory=list)


class StatisticalEvidence(_Frozen):
    """Evidence from the Isolation Forest over session count-vectors."""

    anomaly_score: float = Field(ge=0.0, le=1.0)
    important_features: list[FeatureContribution] = Field(default_factory=list)


class EnsembleEvidence(_Frozen):
    """How the two component scores were combined into the final decision."""

    seq_weight: float
    stat_weight: float
    seq_score: float = Field(ge=0.0, le=1.0)
    stat_score: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    severity: Severity


class Provenance(_Frozen):
    """Where the alert came from — the anchor for verification."""

    session_external_id: str
    dataset: str
    event_count: int = Field(ge=0)
    # ISO-8601 strings (or None) so the object serializes without a datetime codec.
    started_at: str | None = None
    ended_at: str | None = None


class Evidence(_Frozen):
    """The complete, self-contained explanation attached to an alert."""

    sequence: SequenceEvidence
    statistical: StatisticalEvidence
    ensemble: EnsembleEvidence
    provenance: Provenance

    def to_json_dict(self) -> dict[str, object]:
        """Serialize for persistence / API transport."""
        return self.model_dump(mode="json")

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> Evidence:
        return cls.model_validate(data)
