"""Integration tests for the CICIDS-style flow dataset source."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexguard.application.use_cases.ingest_and_parse import IngestAndParse
from nexguard.domain.ports import DatasetSource
from nexguard.infrastructure.datasets.cicids import CicidsDatasetSource
from nexguard.infrastructure.memory.repositories import InMemoryLogRepository
from nexguard.infrastructure.parsing.drain3_miner import Drain3TemplateMiner

pytestmark = pytest.mark.integration

_FIXTURE = Path(__file__).parents[2] / "fixtures" / "cicids" / "cicids_sample.csv"


def test_flows_group_into_labeled_sessions_by_source() -> None:
    source = CicidsDatasetSource(_FIXTURE)
    assert isinstance(source, DatasetSource)

    sessions = {s.external_id: s for s in source.iter_sessions()}
    assert set(sessions) == {
        "cicids_10.0.0.1",
        "cicids_10.0.0.2",
        "cicids_10.0.0.3",
        "cicids_10.0.0.4",
    }
    assert sessions["cicids_10.0.0.1"].label is False  # all benign
    assert sessions["cicids_10.0.0.2"].label is True  # contains DoS Hulk
    assert sessions["cicids_10.0.0.3"].label is False
    assert sessions["cicids_10.0.0.4"].label is True  # PortScan

    # Flows are rendered as structured, templatable event lines.
    assert sessions["cicids_10.0.0.1"].lines[0].startswith("flow protocol=TCP service=HTTP")


async def test_cicids_flows_through_the_pipeline() -> None:
    repo = InMemoryLogRepository()
    use_case = IngestAndParse(Drain3TemplateMiner(), repo)
    sessions = await use_case.execute(CicidsDatasetSource(_FIXTURE).iter_sessions())

    assert len(sessions) == 4
    attack = next(s for s in sessions if s.external_id == "cicids_10.0.0.2")
    assert len(attack.event_id_sequence()) == 4
