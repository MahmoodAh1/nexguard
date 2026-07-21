"""Integration tests for the DeepLog-style LSTM sequence detector."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexguard.domain.value_objects import EventId
from nexguard.infrastructure.detection.sequence_lstm import LstmSequenceDetector

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# A deterministic normal "grammar": events cycle 10 -> 11 -> 12 -> 13 -> 14 -> 15.
_CYCLE = [10, 11, 12, 13, 14, 15]


def _seq(values: list[int]) -> list[EventId]:
    return [EventId(v) for v in values]


def _normal_corpus() -> list[list[EventId]]:
    corpus = []
    for repeats in (1, 2, 3):
        corpus.extend([_seq(_CYCLE * repeats) for _ in range(20)])
    return corpus


def _trained() -> LstmSequenceDetector:
    return LstmSequenceDetector.fit(
        _normal_corpus(),
        window=3,
        embed_dim=16,
        hidden=32,
        epochs=60,
        top_k=1,
        lr=0.05,
        seed=0,
    )


def test_in_grammar_sequence_is_calm_out_of_grammar_is_flagged() -> None:
    detector = _trained()
    normal = detector.score(_seq(_CYCLE))
    # An unknown event (99) plus a broken transition.
    anomalous = detector.score(_seq([10, 11, 12, 99, 14, 15]))

    assert anomalous.anomaly_score > normal.anomaly_score
    assert anomalous.surprising_step_indices  # at least one surprise
    assert normal.anomaly_score <= 0.34


def test_verdict_carries_predicted_vs_actual_evidence() -> None:
    detector = _trained()
    verdict = detector.score(_seq([10, 11, 12, 99, 14, 15]))

    assert verdict.actual_event is not None
    assert verdict.predicted_topk  # the model's expectation at the flagged step
    assert verdict.perplexity >= 0.0
    assert 0.0 <= verdict.confidence <= 1.0
    assert len(verdict.suspicious_subsequence) >= 1


def test_empty_sequence_is_benign() -> None:
    detector = _trained()
    verdict = detector.score([])
    assert verdict.anomaly_score == 0.0


def test_empty_training_set_rejected() -> None:
    with pytest.raises(ValueError):
        LstmSequenceDetector.fit([])


def test_save_and_load_reproduces_score(tmp_path: Path) -> None:
    detector = _trained()
    sample = _seq([10, 11, 12, 99, 14, 15])
    before = detector.score(sample).anomaly_score

    artifact = tmp_path / "lstm.pt"
    detector.save(artifact)
    reloaded = LstmSequenceDetector.load(artifact)
    after = reloaded.score(sample).anomaly_score

    assert before == pytest.approx(after)
