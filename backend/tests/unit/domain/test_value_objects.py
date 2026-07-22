"""Unit tests for domain value objects."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nexguard.domain.value_objects import (
    Confidence,
    CountVector,
    EventId,
    Score,
    Severity,
    TimeRange,
)


class TestScore:
    def test_accepts_unit_interval(self) -> None:
        assert Score(0.0).value == 0.0
        assert Score(1.0).value == 1.0
        assert Score(0.5).value == 0.5

    @pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0, -5.0])
    def test_rejects_out_of_range(self, bad: float) -> None:
        with pytest.raises(ValueError):
            Score(bad)

    def test_rejects_non_number(self) -> None:
        with pytest.raises(TypeError):
            Score(True)

    def test_clamped_squashes_into_range(self) -> None:
        assert Score.clamped(1.7).value == 1.0
        assert Score.clamped(-3.0).value == 0.0
        assert Score.clamped(0.3).value == 0.3

    def test_is_ordered(self) -> None:
        assert Score(0.2) < Score(0.8)
        assert max(Score(0.2), Score(0.9)).value == 0.9


class TestConfidence:
    def test_valid_and_invalid(self) -> None:
        assert Confidence(0.42).value == 0.42
        with pytest.raises(ValueError):
            Confidence(1.5)


class TestSeverity:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (0.0, Severity.LOW),
            (0.39, Severity.LOW),
            (0.40, Severity.MEDIUM),
            (0.59, Severity.MEDIUM),
            (0.60, Severity.HIGH),
            (0.79, Severity.HIGH),
            (0.80, Severity.CRITICAL),
            (1.0, Severity.CRITICAL),
        ],
    )
    def test_from_score_bands(self, score: float, expected: Severity) -> None:
        assert Severity.from_score(score) is expected
        assert Severity.from_score(Score(score)) is expected

    def test_rank_ordering(self) -> None:
        ranks = [s.rank for s in (Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)]
        assert ranks == sorted(ranks)
        assert Severity.CRITICAL.rank > Severity.LOW.rank


class TestTimeRange:
    def test_valid_range_and_duration(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        rng = TimeRange(start=start, end=start + timedelta(seconds=30))
        assert rng.duration == timedelta(seconds=30)

    def test_end_before_start_rejected(self) -> None:
        start = datetime(2026, 1, 1, tzinfo=UTC)
        with pytest.raises(ValueError):
            TimeRange(start=start, end=start - timedelta(seconds=1))

    def test_spanning_empty_is_none(self) -> None:
        assert TimeRange.spanning([]) is None

    def test_spanning_covers_extremes(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=UTC)
        moments = [base + timedelta(seconds=s) for s in (5, 1, 9, 3)]
        rng = TimeRange.spanning(moments)
        assert rng is not None
        assert rng.start == base + timedelta(seconds=1)
        assert rng.end == base + timedelta(seconds=9)


class TestCountVector:
    def test_length_mismatch_rejected(self) -> None:
        with pytest.raises(ValueError):
            CountVector(vocab=(EventId(1), EventId(2)), values=(1.0,))

    def test_from_counts_aligns_to_vocab(self) -> None:
        vocab = [EventId(1), EventId(2), EventId(3)]
        counts = {EventId(1): 4, EventId(3): 2}
        vector = CountVector.from_counts(counts, vocab)
        assert vector.as_list() == [4.0, 0.0, 2.0]
        assert vector.dimension == 3
