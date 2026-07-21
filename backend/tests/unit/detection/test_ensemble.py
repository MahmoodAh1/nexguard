"""Unit tests for the weighted ensemble."""

from __future__ import annotations

import pytest

from nexguard.domain.detection import SequenceVerdict, StatisticalVerdict
from nexguard.domain.value_objects import Severity
from nexguard.infrastructure.detection.ensemble import WeightedEnsemble


def _seq(score: float) -> SequenceVerdict:
    return SequenceVerdict(anomaly_score=score, confidence=0.9, perplexity=2.0)


def _stat(score: float) -> StatisticalVerdict:
    return StatisticalVerdict(anomaly_score=score)


def test_weighted_combination_math() -> None:
    ensemble = WeightedEnsemble(seq_weight=0.5, stat_weight=0.5, threshold=0.5)
    verdict = ensemble.combine(_seq(0.8), _stat(0.2))
    assert verdict.final_score.value == pytest.approx(0.5)
    assert verdict.is_alert is True
    assert verdict.severity is Severity.MEDIUM


def test_weights_are_normalized() -> None:
    ensemble = WeightedEnsemble(seq_weight=3.0, stat_weight=1.0)
    verdict = ensemble.combine(_seq(1.0), _stat(0.0))
    assert verdict.seq_weight == pytest.approx(0.75)
    assert verdict.stat_weight == pytest.approx(0.25)
    assert verdict.final_score.value == pytest.approx(0.75)


def test_both_high_exceeds_one_high() -> None:
    ensemble = WeightedEnsemble(seq_weight=0.6, stat_weight=0.4)
    both = ensemble.combine(_seq(0.9), _stat(0.9))
    one = ensemble.combine(_seq(0.9), _stat(0.1))
    assert both.final_score.value > one.final_score.value


def test_below_threshold_is_not_an_alert() -> None:
    ensemble = WeightedEnsemble(seq_weight=0.5, stat_weight=0.5, threshold=0.6)
    verdict = ensemble.combine(_seq(0.4), _stat(0.4))
    assert verdict.is_alert is False
    assert verdict.severity is Severity.MEDIUM


def test_invalid_weights_rejected() -> None:
    with pytest.raises(ValueError):
        WeightedEnsemble(seq_weight=0.0, stat_weight=0.0)


def test_invalid_threshold_rejected() -> None:
    with pytest.raises(ValueError):
        WeightedEnsemble(threshold=1.5)
