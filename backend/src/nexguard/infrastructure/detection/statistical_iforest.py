"""Isolation Forest statistical detector.

Implements the :class:`~nexguard.domain.ports.StatisticalDetector` port over
session count-vectors. Trained (predominantly) on normal sessions, it flags
sessions whose *composition* is unusual — complementary to the sequence model,
which reasons about *ordering*.

Scoring: Isolation Forest's ``decision_function`` is positive for inliers and
negative for outliers, with the learned boundary at zero. We map it through a
temperature-scaled sigmoid so the anomaly score is in ``[0, 1]`` with the decision
boundary at ``0.5`` — inliers below, outliers above — which lines up with the
ensemble's threshold semantics. The temperature is the spread of training margins,
so the calibration is data-adaptive rather than hand-tuned.

Explainability: Isolation Forest has no native per-feature attribution, so we use
model-agnostic **occlusion** — for each present template, we neutralize its count
to the training baseline and measure how much the anomaly score drops. Templates
whose removal most reduces the score are the ones driving the alert.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

from nexguard.domain.detection import StatisticalVerdict
from nexguard.domain.evidence import FeatureContribution
from nexguard.domain.value_objects import CountVector, EventId

_ARTIFACT_VERSION = 2
_MIN_TEMPERATURE = 1e-3


class IsolationForestDetector:
    """Unsupervised outlier detector over session count-vectors."""

    def __init__(
        self,
        *,
        model: IsolationForest,
        feature_vocab: tuple[EventId, ...],
        baseline: np.ndarray,
        temperature: float,
        templates: dict[int, str] | None = None,
        top_k: int = 5,
    ) -> None:
        self._model = model
        self._feature_vocab = feature_vocab
        self._baseline = baseline
        self._temperature = max(temperature, _MIN_TEMPERATURE)
        self._templates = templates or {}
        self._top_k = top_k

    @property
    def feature_vocab(self) -> tuple[EventId, ...]:
        return self._feature_vocab

    # ── training ──
    @classmethod
    def fit(
        cls,
        count_vectors: list[CountVector],
        *,
        n_estimators: int = 200,
        contamination: float | str = "auto",
        seed: int = 42,
        templates: dict[int, str] | None = None,
        top_k: int = 5,
    ) -> IsolationForestDetector:
        if not count_vectors:
            raise ValueError("cannot fit IsolationForestDetector on zero sessions")

        feature_vocab = cls._union_vocab(count_vectors)
        matrix = np.array(
            [cls._align(cv, feature_vocab) for cv in count_vectors], dtype=float
        )

        model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=seed,
            n_jobs=1,
        )
        model.fit(matrix)

        margins = model.decision_function(matrix)
        return cls(
            model=model,
            feature_vocab=feature_vocab,
            baseline=matrix.mean(axis=0),
            temperature=float(np.std(margins)),
            templates=templates,
            top_k=top_k,
        )

    # ── inference ──
    def score(self, counts: CountVector) -> StatisticalVerdict:
        x = self._align(counts, self._feature_vocab)
        anomaly = self._anomaly(x)
        return StatisticalVerdict(
            anomaly_score=round(anomaly, 6),
            important_features=self._attribution(x, anomaly),
        )

    def _anomaly(self, x: np.ndarray) -> float:
        margin = float(self._model.decision_function(x.reshape(1, -1))[0])
        # sigmoid(-margin / T): margin > 0 (inlier) -> < 0.5, margin < 0 -> > 0.5.
        return 1.0 / (1.0 + math.exp(margin / self._temperature))

    def _attribution(
        self, x: np.ndarray, anomaly: float
    ) -> tuple[FeatureContribution, ...]:
        contributions: list[FeatureContribution] = []
        for index, value in enumerate(x):
            if np.isclose(value, self._baseline[index]):
                continue
            perturbed = x.copy()
            perturbed[index] = self._baseline[index]
            delta = anomaly - self._anomaly(perturbed)
            if delta <= 0:
                continue
            event_id = int(self._feature_vocab[index])
            contributions.append(
                FeatureContribution(
                    event_id=EventId(event_id),
                    template=self._templates.get(event_id),
                    contribution=round(float(delta), 6),
                )
            )
        contributions.sort(key=lambda fc: fc.contribution, reverse=True)
        return tuple(contributions[: self._top_k])

    # ── persistence ──
    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "version": _ARTIFACT_VERSION,
                "model": self._model,
                "feature_vocab": [int(e) for e in self._feature_vocab],
                "baseline": self._baseline,
                "temperature": self._temperature,
                "templates": self._templates,
                "top_k": self._top_k,
            },
            target,
        )

    @classmethod
    def load(cls, path: str | Path) -> IsolationForestDetector:
        # SECURITY: joblib uses pickle, so only ever load artifacts produced by
        # our own ml/ training pipeline from the operator-controlled
        # `model_artifact_dir` — never from untrusted or user-supplied paths.
        state: dict[str, Any] = joblib.load(Path(path))
        return cls(
            model=state["model"],
            feature_vocab=tuple(EventId(e) for e in state["feature_vocab"]),
            baseline=state["baseline"],
            temperature=state["temperature"],
            templates=state.get("templates", {}),
            top_k=state.get("top_k", 5),
        )

    # ── helpers ──
    @staticmethod
    def _union_vocab(count_vectors: list[CountVector]) -> tuple[EventId, ...]:
        seen: dict[EventId, None] = {}
        for cv in count_vectors:
            for event_id in cv.vocab:
                seen.setdefault(event_id, None)
        return tuple(sorted(seen, key=int))

    @staticmethod
    def _align(counts: CountVector, feature_vocab: tuple[EventId, ...]) -> np.ndarray:
        as_map = dict(zip(counts.vocab, counts.values, strict=True))
        return np.array([as_map.get(eid, 0.0) for eid in feature_vocab], dtype=float)
