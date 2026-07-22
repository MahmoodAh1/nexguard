"""Unit tests for detection metrics."""

from __future__ import annotations

import math

import pytest

from nexguard.evaluation.metrics import compute_metrics


def test_perfect_separation() -> None:
    labels = [True, True, False, False]
    scores = [0.9, 0.8, 0.1, 0.2]
    m = compute_metrics(labels, scores, threshold=0.5)

    assert m.precision == 1.0
    assert m.recall == 1.0
    assert m.f1 == 1.0
    assert m.false_positive_rate == 0.0
    assert m.false_negative_rate == 0.0
    assert m.roc_auc == 1.0
    assert m.pr_auc == 1.0
    assert m.confusion.as_dict() == {"tp": 2, "fp": 0, "tn": 2, "fn": 0}


def test_mixed_errors() -> None:
    # One false negative (0.4 on a positive) and one false positive (0.7 on a negative).
    labels = [True, True, False, False]
    scores = [0.9, 0.4, 0.7, 0.2]
    m = compute_metrics(labels, scores, threshold=0.5)

    assert m.confusion.as_dict() == {"tp": 1, "fp": 1, "tn": 1, "fn": 1}
    assert m.precision == pytest.approx(0.5)
    assert m.recall == pytest.approx(0.5)
    assert m.false_positive_rate == pytest.approx(0.5)
    assert m.false_negative_rate == pytest.approx(0.5)


def test_single_class_makes_auc_undefined() -> None:
    m = compute_metrics([False, False, False], [0.1, 0.2, 0.3], threshold=0.5)
    assert math.isnan(m.roc_auc)
    assert math.isnan(m.pr_auc)


def test_zero_division_is_safe() -> None:
    # No positives predicted and none present -> precision/recall default to 0.
    m = compute_metrics([False, False], [0.1, 0.2], threshold=0.5)
    assert m.precision == 0.0
    assert m.recall == 0.0
    assert m.f1 == 0.0


def test_length_mismatch_and_empty_rejected() -> None:
    with pytest.raises(ValueError):
        compute_metrics([True], [0.1, 0.2], threshold=0.5)
    with pytest.raises(ValueError):
        compute_metrics([], [], threshold=0.5)
