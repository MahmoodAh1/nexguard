"""Integration tests for the BGL dataset source (windowed sessions)."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexguard.application.use_cases.ingest_and_parse import IngestAndParse
from nexguard.domain.ports import DatasetSource
from nexguard.infrastructure.datasets.bgl import BglDatasetSource
from nexguard.infrastructure.memory.repositories import InMemoryLogRepository
from nexguard.infrastructure.parsing.drain3_miner import Drain3TemplateMiner

pytestmark = pytest.mark.integration

_FIXTURE = Path(__file__).parents[2] / "fixtures" / "bgl" / "bgl_sample.log"


def test_windows_are_labeled_by_contained_alerts() -> None:
    source = BglDatasetSource(_FIXTURE, window_size=8)
    assert isinstance(source, DatasetSource)

    sessions = list(source.iter_sessions())
    assert len(sessions) == 3  # 24 lines / window 8
    assert [s.label for s in sessions] == [False, True, False]

    for session in sessions:
        assert session.dataset == "bgl"
        assert session.external_id.startswith("bgl_win_")
        assert len(session.lines) == 8
        assert len(session.timestamps) == 8
        assert session.timestamps[0].startswith("2005-")


def test_rejects_invalid_window_size() -> None:
    with pytest.raises(ValueError):
        BglDatasetSource(_FIXTURE, window_size=0)


async def test_bgl_flows_through_the_same_pipeline_as_hdfs() -> None:
    repo = InMemoryLogRepository()
    use_case = IngestAndParse(Drain3TemplateMiner(), repo)
    sessions = await use_case.execute(BglDatasetSource(_FIXTURE, window_size=8).iter_sessions())

    assert len(sessions) == 3
    # The anomalous window parsed into a real event sequence.
    anomalous = next(s for s in sessions if s.label is True)
    assert len(anomalous.event_id_sequence()) == 8
