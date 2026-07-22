"""Unit tests for ensemble weight + threshold calibration."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexguard.evaluation.calibration import (
    EnsembleCalibration,
    calibrate_ensemble,
    sweep_threshold,
)

# A clean separator: positives high, negatives low.
_SEQ = [0.9] * 10 + [0.1] * 10
_LABELS = [True] * 10 + [False] * 10
# An *inverted*, misleading statistical signal — a stat-heavy blend cannot be
# rescued by any threshold, so calibration must shift weight to the sequence model.
_STAT = [0.1] * 10 + [0.9] * 10


def test_sweep_threshold_finds_separating_threshold() -> None:
    point = sweep_threshold(_LABELS, _SEQ, objective="f1")
    assert point.f1 == 1.0
    assert 0.1 < point.threshold <= 0.9


def test_calibration_improves_a_miscalibrated_default() -> None:
    # A stat-leaning default trusts the misleading detector -> useless.
    calibration = calibrate_ensemble(
        _SEQ, _STAT, _LABELS, default_seq_weight=0.3, default_threshold=0.5
    )
    assert calibration.before.f1 == pytest.approx(0.0)  # ranks the wrong class higher
    assert calibration.after.f1 == 1.0
    assert calibration.after.f1 > calibration.before.f1
    assert (
        calibration.seq_weight >= 0.6
    )  # learned to down-weight the misleading detector


def test_target_fpr_objective_caps_false_positives() -> None:
    calibration = calibrate_ensemble(
        _SEQ, _STAT, _LABELS, objective="target_fpr", target_fpr=0.0
    )
    assert calibration.after.false_positive_rate == 0.0
    assert calibration.after.recall == 1.0


def test_length_mismatch_rejected() -> None:
    with pytest.raises(ValueError):
        calibrate_ensemble([0.1, 0.2], [0.3], [True, False])


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    calibration = calibrate_ensemble(_SEQ, _STAT, _LABELS, default_seq_weight=0.0)
    path = tmp_path / "calibration.json"
    calibration.save(path)
    loaded = EnsembleCalibration.load(path)
    assert loaded == calibration
