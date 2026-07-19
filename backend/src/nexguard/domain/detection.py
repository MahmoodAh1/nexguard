"""Detection result types — the verdicts detectors return.

These are structured value objects (frozen dataclasses) produced by the detector
ports and consumed by the ensemble, the explainer, and the use cases. Keeping
them here (rather than in an adapter) means the application layer depends only on
the domain's vocabulary, never on PyTorch/sklearn types.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from nexguard.domain.evidence import FeatureContribution
from nexguard.domain.value_objects import EventId, Score, Severity


@dataclass(frozen=True, slots=True)
class TemplateMatch:
    """The result of mining a single raw log line into a template."""

    event_id: EventId
    template: str
    parameters: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SequenceVerdict:
    """DeepLog-style next-event-prediction verdict for one session."""

    anomaly_score: float
    confidence: float
    perplexity: float
    actual_event: EventId | None = None
    predicted_topk: tuple[EventId, ...] = ()
    surprising_step_indices: tuple[int, ...] = ()
    suspicious_subsequence: tuple[EventId, ...] = ()


@dataclass(frozen=True, slots=True)
class StatisticalVerdict:
    """Isolation-Forest verdict for one session's count-vector."""

    anomaly_score: float
    important_features: tuple[FeatureContribution, ...] = ()


@dataclass(frozen=True, slots=True)
class EnsembleVerdict:
    """The combined decision from the ensemble layer."""

    seq_score: float
    stat_score: float
    final_score: Score
    severity: Severity
    is_alert: bool
    seq_weight: float
    stat_weight: float
    threshold: float


@dataclass(frozen=True, slots=True)
class RawSession:
    """Raw, un-parsed session as produced by a dataset source."""

    external_id: str
    dataset: str
    lines: tuple[str, ...]
    label: bool | None = None
    timestamps: tuple[str, ...] = field(default=())
