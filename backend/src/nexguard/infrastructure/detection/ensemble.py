"""Weighted-vote ensemble.

Implements the :class:`~nexguard.domain.ports.Ensemble` port. Combines the
sequence and statistical anomaly scores via configurable, normalized weights,
applies a decision threshold, and derives severity from the final score. Weights,
threshold, and severity bands are configuration — recalibrated by the feedback
loop and tracked in MLflow.
"""

from __future__ import annotations

from nexguard.domain.detection import (
    EnsembleVerdict,
    SequenceVerdict,
    StatisticalVerdict,
)
from nexguard.domain.value_objects import Score, Severity


class WeightedEnsemble:
    """Configurable weighted combination of the two detectors."""

    def __init__(
        self,
        *,
        seq_weight: float = 0.6,
        stat_weight: float = 0.4,
        threshold: float = 0.5,
        severity_bands: tuple[float, float, float] = (0.40, 0.60, 0.80),
    ) -> None:
        total = seq_weight + stat_weight
        if total <= 0:
            raise ValueError("ensemble weights must sum to a positive value")
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be in [0, 1]")
        # Normalize so the final score stays in [0, 1] regardless of input weights.
        self._seq_weight = seq_weight / total
        self._stat_weight = stat_weight / total
        self._threshold = threshold
        self._severity_bands = severity_bands

    def combine(
        self, sequence: SequenceVerdict, statistical: StatisticalVerdict
    ) -> EnsembleVerdict:
        seq_score = _unit(sequence.anomaly_score)
        stat_score = _unit(statistical.anomaly_score)
        final = self._seq_weight * seq_score + self._stat_weight * stat_score
        score = Score.clamped(final)
        return EnsembleVerdict(
            seq_score=seq_score,
            stat_score=stat_score,
            final_score=score,
            severity=Severity.from_score(score, self._severity_bands),
            is_alert=score.value >= self._threshold,
            seq_weight=self._seq_weight,
            stat_weight=self._stat_weight,
            threshold=self._threshold,
        )


def _unit(value: float) -> float:
    return min(1.0, max(0.0, float(value)))
