"""Integration tests for the Isolation Forest statistical detector.

Isolation Forest detects low-density regions *within* the training support (it
cannot extrapolate beyond a feature's observed range), so these tests use
realistic multinomial-distributed count vectors — the shape of real session
composition — rather than degenerate fixed counts.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from nexguard.domain.value_objects import CountVector, EventId
from nexguard.infrastructure.detection.statistical_iforest import (
    IsolationForestDetector,
)

pytestmark = pytest.mark.integration

_VOCAB = tuple(EventId(i) for i in (1, 2, 3, 4, 5))
# Normal composition: event 1 (alloc) is rare; events 2-5 carry most of the mass.
_NORMAL_PROBS = [0.08, 0.25, 0.25, 0.22, 0.20]


def _cv(counts: list[float]) -> CountVector:
    mapping = {EventId(i + 1): counts[i] for i in range(len(counts))}
    return CountVector.from_counts(mapping, _VOCAB)


def _normal_vectors(n: int = 120, seed: int = 0) -> list[CountVector]:
    rng = np.random.default_rng(seed)
    return [_cv(list(rng.multinomial(15, _NORMAL_PROBS).astype(float))) for _ in range(n)]


_TEMPLATES = {1: "allocateBlock", 5: "addStoredBlock"}


def test_outlier_scores_higher_than_normal() -> None:
    detector = IsolationForestDetector.fit(_normal_vectors(), templates=_TEMPLATES, seed=42)
    normal = detector.score(_cv([1, 4, 4, 3, 3]))
    # Composition shifted heavily onto the normally-rare event 1.
    outlier = detector.score(_cv([12, 1, 1, 0, 1]))

    assert 0.0 <= normal.anomaly_score <= 1.0
    assert normal.anomaly_score < 0.5
    assert outlier.anomaly_score > normal.anomaly_score
    assert outlier.anomaly_score >= 0.5


def test_attribution_identifies_the_deviating_template() -> None:
    detector = IsolationForestDetector.fit(_normal_vectors(), templates=_TEMPLATES, seed=42)
    outlier = detector.score(_cv([12, 1, 1, 0, 1]))

    assert outlier.important_features  # non-empty
    top = outlier.important_features[0]
    assert int(top.event_id) == 1  # the template whose share exploded
    assert top.template == "allocateBlock"
    assert top.contribution > 0


def test_empty_training_set_rejected() -> None:
    with pytest.raises(ValueError):
        IsolationForestDetector.fit([])


def test_save_and_load_preserves_scores(tmp_path: Path) -> None:
    detector = IsolationForestDetector.fit(_normal_vectors(), templates=_TEMPLATES, seed=42)
    sample = _cv([12, 1, 1, 0, 1])
    before = detector.score(sample).anomaly_score

    artifact = tmp_path / "iforest.joblib"
    detector.save(artifact)
    reloaded = IsolationForestDetector.load(artifact)
    after = reloaded.score(sample).anomaly_score

    assert before == pytest.approx(after)
    assert reloaded.feature_vocab == detector.feature_vocab
