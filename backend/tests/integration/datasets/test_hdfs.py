"""Integration tests for the HDFS dataset source (grouping + labels)."""

from __future__ import annotations

from pathlib import Path

import pytest

from nexguard.infrastructure.datasets.hdfs import HdfsDatasetSource

pytestmark = pytest.mark.integration


def test_groups_lines_into_labeled_sessions(
    hdfs_log_path: Path, hdfs_label_path: Path
) -> None:
    source = HdfsDatasetSource(hdfs_log_path, hdfs_label_path)
    sessions = list(source.iter_sessions())

    # Fixture has 70 blocks (60 normal + 10 anomalous).
    assert len(sessions) == 70
    assert sum(1 for s in sessions if s.label is True) == 10
    assert sum(1 for s in sessions if s.label is False) == 60

    for session in sessions:
        assert session.dataset == "hdfs"
        assert session.external_id.startswith("blk_")
        assert len(session.lines) >= 1
        # Every line in a session references that block id.
        assert all(session.external_id in line for line in session.lines)
        # Timestamps are parsed to ISO-8601 and aligned to lines.
        assert len(session.timestamps) == len(session.lines)
        assert session.timestamps[0].startswith("2008-11-09T")


def test_missing_label_file_yields_unlabeled_sessions(hdfs_log_path: Path) -> None:
    source = HdfsDatasetSource(hdfs_log_path, label_path=None)
    sessions = list(source.iter_sessions())
    assert len(sessions) == 70
    assert all(s.label is None for s in sessions)
