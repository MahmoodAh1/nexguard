"""Domain value objects.

Value objects are immutable and compared by value. They encapsulate the small
invariants of the domain (a score is in ``[0, 1]``, a time range does not end
before it starts) so those invariants cannot be violated anywhere in the system.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import NewType

# A stable identifier for a log template (Drain3 cluster). The same template text
# always maps to the same ``EventId`` across restarts, and across train/serve.
EventId = NewType("EventId", int)


def _ensure_unit_interval(value: float, name: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be a real number, got {type(value).__name__}")
    if not (0.0 <= float(value) <= 1.0):
        raise ValueError(f"{name} must be in [0, 1], got {value}")


@dataclass(frozen=True, order=True, slots=True)
class Score:
    """A normalized anomaly score in ``[0, 1]`` (higher = more anomalous)."""

    value: float

    def __post_init__(self) -> None:
        _ensure_unit_interval(self.value, "Score")

    @classmethod
    def clamped(cls, value: float) -> Score:
        """Construct a score, clamping raw model output into ``[0, 1]``."""
        return cls(min(1.0, max(0.0, float(value))))


@dataclass(frozen=True, order=True, slots=True)
class Confidence:
    """Model confidence in a prediction, in ``[0, 1]``."""

    value: float

    def __post_init__(self) -> None:
        _ensure_unit_interval(self.value, "Confidence")

    @classmethod
    def clamped(cls, value: float) -> Confidence:
        return cls(min(1.0, max(0.0, float(value))))


# Default severity bands: upper-exclusive thresholds mapping score -> severity.
# score < 0.40 -> LOW, < 0.60 -> MEDIUM, < 0.80 -> HIGH, else CRITICAL.
_DEFAULT_BANDS: tuple[float, float, float] = (0.40, 0.60, 0.80)


class Severity(StrEnum):
    """Alert severity, derived from the ensemble score via banding."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _SEVERITY_RANK[self]

    @classmethod
    def from_score(
        cls,
        score: Score | float,
        bands: tuple[float, float, float] = _DEFAULT_BANDS,
    ) -> Severity:
        value = score.value if isinstance(score, Score) else float(score)
        low_hi, med_hi, high_hi = bands
        if value < low_hi:
            return cls.LOW
        if value < med_hi:
            return cls.MEDIUM
        if value < high_hi:
            return cls.HIGH
        return cls.CRITICAL


_SEVERITY_RANK: dict[Severity, int] = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


@dataclass(frozen=True, slots=True)
class TimeRange:
    """A closed time interval ``[start, end]``."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(
                f"TimeRange end {self.end!r} precedes start {self.start!r}"
            )

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    @classmethod
    def spanning(cls, moments: Iterable[datetime]) -> TimeRange | None:
        """Build the tightest range covering all given moments, or None if empty."""
        ordered = sorted(moments)
        if not ordered:
            return None
        return cls(start=ordered[0], end=ordered[-1])


@dataclass(frozen=True, slots=True)
class CountVector:
    """An ordered feature vector of event counts, aligned to a fixed vocabulary.

    ``vocab[i]`` is the :class:`EventId` whose count is ``values[i]``. Keeping the
    vocabulary attached to the vector guarantees the statistical detector always
    receives features in a consistent, self-describing order.
    """

    vocab: tuple[EventId, ...]
    values: tuple[float, ...] = field()

    def __post_init__(self) -> None:
        if len(self.vocab) != len(self.values):
            raise ValueError(
                f"CountVector vocab/values length mismatch: "
                f"{len(self.vocab)} != {len(self.values)}"
            )

    @classmethod
    def from_counts(
        cls, counts: Mapping[EventId, float], vocab: Sequence[EventId]
    ) -> CountVector:
        ordered_vocab = tuple(vocab)
        values = tuple(float(counts.get(event_id, 0)) for event_id in ordered_vocab)
        return cls(vocab=ordered_vocab, values=values)

    def as_list(self) -> list[float]:
        return list(self.values)

    @property
    def dimension(self) -> int:
        return len(self.vocab)
