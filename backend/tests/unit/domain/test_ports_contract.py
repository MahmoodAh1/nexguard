"""Ports are structurally-typed Protocols.

This test proves an adapter needs no explicit inheritance to satisfy a port — it
just has to match the shape. Full signature conformance is enforced by mypy; this
guards the runtime-checkable structural contract.
"""

from __future__ import annotations

from collections.abc import Sequence

from nexguard.domain.detection import SequenceVerdict, TemplateMatch
from nexguard.domain.entities import Template
from nexguard.domain.ports import PasswordHasher, SequenceDetector, TemplateMiner
from nexguard.domain.value_objects import EventId


class _FakeMiner:
    def mine(self, line: str) -> TemplateMatch:
        return TemplateMatch(event_id=EventId(1), template=line)

    def vocabulary(self) -> list[Template]:
        return []


class _FakeSequenceDetector:
    def score(self, sequence: Sequence[EventId]) -> SequenceVerdict:
        return SequenceVerdict(anomaly_score=0.0, confidence=1.0, perplexity=1.0)


class _FakeHasher:
    def hash(self, password: str) -> str:
        return password[::-1]

    def verify(self, password: str, password_hash: str) -> bool:
        return password[::-1] == password_hash


def test_structural_conformance() -> None:
    assert isinstance(_FakeMiner(), TemplateMiner)
    assert isinstance(_FakeSequenceDetector(), SequenceDetector)
    assert isinstance(_FakeHasher(), PasswordHasher)


def test_non_conforming_object_is_not_an_instance() -> None:
    assert not isinstance(object(), TemplateMiner)
