"""Model-comparison harness.

Trains the LSTM, Transformer, Isolation Forest, and Ensemble on the *normal*
sessions of a labeled set and evaluates all four on the full labeled set, so they
can be compared on identical data. Reusable by the ``ml/`` runner and tests.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from nexguard.domain.entities import Session
from nexguard.domain.ports import ExperimentTracker
from nexguard.domain.value_objects import CountVector
from nexguard.evaluation.evaluator import Evaluator, ModelReport
from nexguard.infrastructure.detection.ensemble import WeightedEnsemble
from nexguard.infrastructure.detection.sequence_lstm import LstmSequenceDetector
from nexguard.infrastructure.detection.sequence_transformer import (
    TransformerSequenceDetector,
)
from nexguard.infrastructure.detection.statistical_iforest import (
    IsolationForestDetector,
)


@dataclass(frozen=True)
class ComparisonResult:
    reports: list[ModelReport]
    threshold: float

    def best_by_f1(self) -> ModelReport:
        return max(self.reports, key=lambda report: _nan_to_neg(report.metrics.f1))

    def as_table(self) -> str:
        headers = [
            "Model",
            "Precision",
            "Recall",
            "F1",
            "ROC-AUC",
            "PR-AUC",
            "FPR",
            "FNR",
            "p95 ms",
            "sess/s",
            "alerts/10k",
        ]
        keys = [
            "precision",
            "recall",
            "f1",
            "roc_auc",
            "pr_auc",
            "fpr",
            "fnr",
            "p95_latency_ms",
            "throughput_per_sec",
            "alerts_per_10k",
        ]
        lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
        for report in self.reports:
            row = report.as_row()
            cells = [str(row["model"])] + [str(row[key]) for key in keys]
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)


def _cv(session: Session) -> CountVector:
    counts = session.event_counts()
    return CountVector.from_counts(counts, tuple(counts.keys()))


def _nan_to_neg(value: float) -> float:
    return value if value == value else -1.0  # NaN != NaN


def run_comparison(
    sessions: Sequence[Session],
    *,
    threshold: float = 0.5,
    top_k: int = 2,
    lstm_epochs: int = 15,
    transformer_epochs: int = 40,
    seq_weight: float = 0.6,
    stat_weight: float = 0.4,
    seed: int = 42,
    tracker: ExperimentTracker | None = None,
    dataset: str = "hdfs",
) -> ComparisonResult:
    labeled = [s for s in sessions if s.label is not None]
    if not labeled:
        raise ValueError("comparison requires labeled sessions")
    normal = [s for s in labeled if s.label is False]
    if not normal:
        raise ValueError("comparison requires normal sessions to train on")

    labels = [bool(s.label) for s in labeled]
    normal_sequences = [s.event_id_sequence() for s in normal]

    lstm = LstmSequenceDetector.fit(normal_sequences, epochs=lstm_epochs, top_k=top_k, seed=seed)
    transformer = TransformerSequenceDetector.fit(
        normal_sequences, epochs=transformer_epochs, top_k=top_k, seed=seed
    )
    iforest = IsolationForestDetector.fit([_cv(s) for s in normal], seed=seed)
    ensemble = WeightedEnsemble(seq_weight=seq_weight, stat_weight=stat_weight, threshold=threshold)

    evaluator = Evaluator(threshold=threshold)
    reports = [
        evaluator.evaluate(
            "LSTM",
            labeled,
            labels,
            lambda s: lstm.score(s.event_id_sequence()).anomaly_score,
        ),
        evaluator.evaluate(
            "Transformer",
            labeled,
            labels,
            lambda s: transformer.score(s.event_id_sequence()).anomaly_score,
        ),
        evaluator.evaluate(
            "IsolationForest",
            labeled,
            labels,
            lambda s: iforest.score(_cv(s)).anomaly_score,
        ),
        evaluator.evaluate(
            "Ensemble",
            labeled,
            labels,
            lambda s: (
                ensemble.combine(
                    lstm.score(s.event_id_sequence()), iforest.score(_cv(s))
                ).final_score.value
            ),
        ),
    ]

    if tracker is not None:
        for report in reports:
            tracker.log_run(
                run_name=report.name,
                params={
                    "model": report.name,
                    "dataset": dataset,
                    "threshold": threshold,
                    "top_k": top_k,
                    "seed": seed,
                    "train_normal_sessions": len(normal),
                },
                metrics={
                    **report.metrics.as_dict(),
                    "p50_latency_ms": report.latency_ms_p50,
                    "p95_latency_ms": report.latency_ms_p95,
                    "throughput_per_sec": report.throughput_per_sec,
                    "alerts_per_10k": report.alerts_per_10k,
                },
                tags={"dataset": dataset, "phase": "model-comparison"},
            )

    return ComparisonResult(reports=reports, threshold=threshold)
