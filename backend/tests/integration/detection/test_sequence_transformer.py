"""Integration tests for the Transformer-encoder sequence detector."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexguard.domain.ports import SequenceDetector
from nexguard.domain.value_objects import EventId
from nexguard.infrastructure.detection.sequence_transformer import (
    TransformerSequenceDetector,
)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_CYCLE = [10, 11, 12, 13, 14, 15]


def _seq(values: list[int]) -> list[EventId]:
    return [EventId(v) for v in values]


def _corpus() -> list[list[EventId]]:
    corpus = []
    for repeats in (1, 2, 3):
        corpus.extend([_seq(_CYCLE * repeats) for _ in range(20)])
    return corpus


def _trained() -> TransformerSequenceDetector:
    return TransformerSequenceDetector.fit(
        _corpus(),
        window=3,
        embed_dim=16,
        nhead=2,
        layers=2,
        dim_feedforward=32,
        epochs=120,
        top_k=1,
        lr=5e-3,
        seed=0,
    )


def test_satisfies_sequence_detector_port() -> None:
    assert isinstance(_trained(), SequenceDetector)


def test_out_of_grammar_scores_higher_than_in_grammar() -> None:
    detector = _trained()
    normal = detector.score(_seq(_CYCLE))
    anomalous = detector.score(_seq([10, 11, 12, 99, 14, 15]))

    assert anomalous.anomaly_score > normal.anomaly_score
    assert anomalous.surprising_step_indices
    assert normal.anomaly_score <= 0.34


def test_verdict_fields_populated() -> None:
    verdict = _trained().score(_seq([10, 11, 12, 99, 14, 15]))
    assert verdict.actual_event is not None
    assert verdict.predicted_topk
    assert 0.0 <= verdict.confidence <= 1.0


def test_embed_dim_must_divide_nhead() -> None:
    with pytest.raises(ValueError):
        TransformerSequenceDetector.fit(_corpus(), embed_dim=16, nhead=3)


def test_empty_training_set_rejected() -> None:
    with pytest.raises(ValueError):
        TransformerSequenceDetector.fit([])


def test_save_and_load_reproduces_score(tmp_path: Path) -> None:
    detector = _trained()
    sample = _seq([10, 11, 12, 99, 14, 15])
    before = detector.score(sample).anomaly_score

    artifact = tmp_path / "transformer.pt"
    detector.save(artifact)
    reloaded = TransformerSequenceDetector.load(artifact)
    after = reloaded.score(sample).anomaly_score

    assert before == pytest.approx(after)
