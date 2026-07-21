"""Integration test for the IngestAndParse use case (real miner + in-memory repos)."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexguard.application.use_cases.ingest_and_parse import IngestAndParse
from nexguard.infrastructure.datasets.hdfs import HdfsDatasetSource
from nexguard.infrastructure.memory.repositories import (
    InMemoryLogRepository,
    InMemoryTemplateRepository,
)
from nexguard.infrastructure.parsing.drain3_miner import Drain3TemplateMiner

pytestmark = pytest.mark.integration


async def test_ingest_produces_persisted_labeled_sessions(
    hdfs_log_path: Path, hdfs_label_path: Path
) -> None:
    log_repo = InMemoryLogRepository()
    template_repo = InMemoryTemplateRepository()
    use_case = IngestAndParse(Drain3TemplateMiner(), log_repo, template_repo)

    source = HdfsDatasetSource(hdfs_log_path, hdfs_label_path)
    sessions = await use_case.execute(source.iter_sessions())

    assert len(sessions) == 70

    # Sessions are persisted and retrievable, with event-id sequences populated.
    stored = await log_repo.get_session_by_external_id("hdfs", sessions[0].external_id)
    assert stored is not None
    assert len(stored.event_id_sequence()) == stored.event_count > 0
    assert all(isinstance(int(eid), int) for eid in stored.event_id_sequence())

    # A normal block should have host tokens captured for later verification.
    normal = next(s for s in sessions if s.label is False)
    joined_params = {k: v for e in normal.events for k, v in e.params.items()}
    assert any(key.startswith("ip_") for key in joined_params)

    # The mined vocabulary is upserted and small (HDFS has few distinct templates).
    vocab = await template_repo.all()
    assert 3 <= len(vocab) <= 40


async def test_anomalous_and_normal_have_distinct_sequence_shapes(
    hdfs_log_path: Path, hdfs_label_path: Path
) -> None:
    log_repo = InMemoryLogRepository()
    use_case = IngestAndParse(Drain3TemplateMiner(), log_repo)
    sessions = await use_case.execute(
        HdfsDatasetSource(hdfs_log_path, hdfs_label_path).iter_sessions()
    )

    normal_seqs = [tuple(s.event_id_sequence()) for s in sessions if s.label is False]
    anomalous_seqs = {tuple(s.event_id_sequence()) for s in sessions if s.label is True}

    # At least one anomalous session has a sequence never seen among normal ones.
    normal_set = set(normal_seqs)
    assert any(seq not in normal_set for seq in anomalous_seqs)
