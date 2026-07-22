"""Detection quality metrics.

Computes the classification metrics a SOC cares about from ground-truth labels and
continuous anomaly scores: precision, recall, F1, ROC-AUC, PR-AUC, the confusion
matrix, and the false-positive / false-negative rates. Threshold-independent
metrics (ROC-AUC, PR-AUC) use the continuous scores; the rest use the operating
threshold. All are zero-division safe.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from sklearn.metrics import average_precision_score, roc_auc_score


@dataclass(frozen=True)
class ConfusionMatrix:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int

    def as_dict(self) -> dict[str, int]:
        return {
            "tp": self.true_positive,
            "fp": self.false_positive,
            "tn": self.true_negative,
            "fn": self.false_negative,
        }


@dataclass(frozen=True)
class DetectionMetrics:
    """Threshold-dependent + threshold-independent detection metrics."""

    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    false_positive_rate: float
    false_negative_rate: float
    confusion: ConfusionMatrix
    support: int

    def as_dict(self) -> dict[str, float]:
        return {
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "roc_auc": self.roc_auc,
            "pr_auc": self.pr_auc,
            "false_positive_rate": self.false_positive_rate,
            "false_negative_rate": self.false_negative_rate,
        }


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def compute_metrics(
    labels: Sequence[bool], scores: Sequence[float], *, threshold: float
) -> DetectionMetrics:
    if len(labels) != len(scores):
        raise ValueError("labels and scores must have the same length")
    if not labels:
        raise ValueError("cannot compute metrics on an empty set")

    predictions = [score >= threshold for score in scores]
    tp = sum(1 for label, pred in zip(labels, predictions, strict=True) if label and pred)
    fp = sum(1 for label, pred in zip(labels, predictions, strict=True) if not label and pred)
    tn = sum(1 for label, pred in zip(labels, predictions, strict=True) if not label and not pred)
    fn = sum(1 for label, pred in zip(labels, predictions, strict=True) if label and not pred)

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)

    return DetectionMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        roc_auc=_auc(roc_auc_score, labels, scores),
        pr_auc=_auc(average_precision_score, labels, scores),
        false_positive_rate=_safe_div(fp, fp + tn),
        false_negative_rate=_safe_div(fn, fn + tp),
        confusion=ConfusionMatrix(tp, fp, tn, fn),
        support=len(labels),
    )


def _auc(metric_fn: object, labels: Sequence[bool], scores: Sequence[float]) -> float:
    # ROC/PR-AUC are undefined when only one class is present.
    if len(set(labels)) < 2:
        return math.nan
    try:
        return float(metric_fn([int(label) for label in labels], list(scores)))  # type: ignore[operator]
    except ValueError:
        return math.nan
