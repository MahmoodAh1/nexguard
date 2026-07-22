"""Ensemble weight + threshold calibration.

Given the component (sequence, statistical) anomaly scores and ground-truth labels
on a validation split, searches the ensemble weight blend and decision threshold
for a chosen operating point — maximum F1, or maximum recall subject to a false-
positive-rate cap (the SOC-realistic objective: "flag as much as possible without
drowning analysts"). Reports before/after metrics so the improvement is auditable,
and the chosen parameters persist as a snapshot the ensemble can load.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from nexguard.evaluation.metrics import compute_metrics

Objective = Literal["f1", "target_fpr"]
_ARTIFACT_VERSION = 1


@dataclass(frozen=True)
class OperatingPoint:
    threshold: float
    precision: float
    recall: float
    f1: float
    false_positive_rate: float


@dataclass(frozen=True)
class EnsembleCalibration:
    seq_weight: float
    stat_weight: float
    threshold: float
    objective: str
    before: OperatingPoint
    after: OperatingPoint
    created_at: str

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": _ARTIFACT_VERSION, **asdict(self)}
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> EnsembleCalibration:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            seq_weight=data["seq_weight"],
            stat_weight=data["stat_weight"],
            threshold=data["threshold"],
            objective=data["objective"],
            before=OperatingPoint(**data["before"]),
            after=OperatingPoint(**data["after"]),
            created_at=data["created_at"],
        )


def _operating_point(
    labels: Sequence[bool], scores: Sequence[float], threshold: float
) -> OperatingPoint:
    m = compute_metrics(labels, scores, threshold=threshold)
    return OperatingPoint(
        threshold=threshold,
        precision=m.precision,
        recall=m.recall,
        f1=m.f1,
        false_positive_rate=m.false_positive_rate,
    )


def _threshold_grid(steps: int = 101) -> list[float]:
    return [round(i / (steps - 1), 6) for i in range(steps)]


def sweep_threshold(
    labels: Sequence[bool],
    scores: Sequence[float],
    *,
    objective: Objective = "f1",
    target_fpr: float = 0.05,
) -> OperatingPoint:
    """Pick the best decision threshold for a single score vector."""
    points = [_operating_point(labels, scores, t) for t in _threshold_grid()]
    if objective == "f1":
        return max(points, key=lambda p: (p.f1, p.recall))
    # target_fpr: highest recall while keeping FPR <= cap; fall back to lowest FPR.
    within = [p for p in points if p.false_positive_rate <= target_fpr]
    candidates = within or points
    key = (lambda p: (p.recall, p.f1)) if within else (lambda p: (-p.false_positive_rate, p.recall))
    return max(candidates, key=key)


def calibrate_ensemble(
    seq_scores: Sequence[float],
    stat_scores: Sequence[float],
    labels: Sequence[bool],
    *,
    objective: Objective = "f1",
    target_fpr: float = 0.05,
    default_seq_weight: float = 0.6,
    default_threshold: float = 0.5,
    weight_steps: int = 11,
) -> EnsembleCalibration:
    """Search weight blend + threshold; report before/after operating points."""
    if not (len(seq_scores) == len(stat_scores) == len(labels)):
        raise ValueError("seq_scores, stat_scores, and labels must have equal length")

    def blend(seq_weight: float) -> list[float]:
        stat_weight = 1.0 - seq_weight
        return [
            seq_weight * s + stat_weight * t for s, t in zip(seq_scores, stat_scores, strict=True)
        ]

    before = _operating_point(labels, blend(default_seq_weight), default_threshold)

    def objective_key(point: OperatingPoint) -> tuple[float, float]:
        # F1 objective ranks by F1 (recall tiebreak); target_fpr ranks by recall.
        return (point.f1, point.recall) if objective == "f1" else (point.recall, point.f1)

    best: tuple[float, OperatingPoint] | None = None
    for step in range(weight_steps):
        seq_weight = round(step / (weight_steps - 1), 6)
        point = sweep_threshold(
            labels, blend(seq_weight), objective=objective, target_fpr=target_fpr
        )
        if best is None or objective_key(point) > objective_key(best[1]):
            best = (seq_weight, point)

    assert best is not None
    seq_weight, after = best
    return EnsembleCalibration(
        seq_weight=seq_weight,
        stat_weight=round(1.0 - seq_weight, 6),
        threshold=after.threshold,
        objective=objective,
        before=before,
        after=after,
        created_at=datetime.now(tz=UTC).isoformat(),
    )
