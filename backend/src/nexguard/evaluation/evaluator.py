"""Per-model evaluation: detection quality + operational cost.

Runs a model's scoring function over a labeled set, timing each call, then reports
detection metrics alongside the operational metrics a SOC lead needs to reason
about analyst workload: inference latency (p50/p95), throughput, and — crucially —
**alerts per 10k sessions**, which multiplied by volume is the daily triage load.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import perf_counter

from nexguard.domain.entities import Session
from nexguard.evaluation.metrics import DetectionMetrics, compute_metrics

ScoreFn = Callable[[Session], float]


@dataclass(frozen=True)
class ModelReport:
    name: str
    metrics: DetectionMetrics
    latency_ms_p50: float
    latency_ms_p95: float
    throughput_per_sec: float
    alerts_per_10k: float

    def as_row(self) -> dict[str, float | str]:
        m = self.metrics
        return {
            "model": self.name,
            "precision": round(m.precision, 4),
            "recall": round(m.recall, 4),
            "f1": round(m.f1, 4),
            "roc_auc": round(m.roc_auc, 4),
            "pr_auc": round(m.pr_auc, 4),
            "fpr": round(m.false_positive_rate, 4),
            "fnr": round(m.false_negative_rate, 4),
            "p95_latency_ms": round(self.latency_ms_p95, 3),
            "throughput_per_sec": round(self.throughput_per_sec, 1),
            "alerts_per_10k": round(self.alerts_per_10k, 1),
        }


class Evaluator:
    """Scores a labeled set and reports quality + operational metrics."""

    def __init__(self, *, threshold: float = 0.5) -> None:
        self._threshold = threshold

    def evaluate(
        self,
        name: str,
        sessions: Sequence[Session],
        labels: Sequence[bool],
        score_fn: ScoreFn,
    ) -> ModelReport:
        if not sessions:
            raise ValueError("cannot evaluate on zero sessions")

        scores: list[float] = []
        latencies_ms: list[float] = []
        for session in sessions:
            started = perf_counter()
            score = score_fn(session)
            latencies_ms.append((perf_counter() - started) * 1000.0)
            scores.append(score)

        metrics = compute_metrics(labels, scores, threshold=self._threshold)
        n = len(sessions)
        alerts = sum(1 for score in scores if score >= self._threshold)
        total_seconds = sum(latencies_ms) / 1000.0

        return ModelReport(
            name=name,
            metrics=metrics,
            latency_ms_p50=_percentile(latencies_ms, 50),
            latency_ms_p95=_percentile(latencies_ms, 95),
            throughput_per_sec=(n / total_seconds if total_seconds > 0 else float("inf")),
            alerts_per_10k=(alerts / n) * 10_000,
        )


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] * (1 - frac) + ordered[high] * frac
