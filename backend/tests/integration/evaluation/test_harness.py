"""Integration test for the model-comparison harness on the HDFS fixture."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from nexguard.application.use_cases.ingest_and_parse import IngestAndParse
from nexguard.domain.entities import Session
from nexguard.evaluation.harness import run_calibration, run_comparison
from nexguard.infrastructure.datasets.hdfs import HdfsDatasetSource
from nexguard.infrastructure.memory.repositories import InMemoryLogRepository
from nexguard.infrastructure.parsing.drain3_miner import Drain3TemplateMiner

pytestmark = [pytest.mark.integration, pytest.mark.slow]


class _RecordingTracker:
    """A fake ExperimentTracker that captures what the harness logs."""

    def __init__(self) -> None:
        self.runs: list[tuple[str, dict[str, float]]] = []

    def log_run(
        self,
        *,
        run_name: str,
        params: Mapping[str, object],
        metrics: Mapping[str, float],
        tags: Mapping[str, str] | None = None,
        artifacts: Sequence[Path] = (),
    ) -> None:
        self.runs.append((run_name, dict(metrics)))


async def _sessions(log: Path, labels: Path) -> list[Session]:
    repo = InMemoryLogRepository()
    use_case = IngestAndParse(Drain3TemplateMiner(), repo)
    return await use_case.execute(HdfsDatasetSource(log, labels).iter_sessions())


async def test_comparison_reports_all_models(hdfs_log_path: Path, hdfs_label_path: Path) -> None:
    sessions = await _sessions(hdfs_log_path, hdfs_label_path)
    tracker = _RecordingTracker()
    result = run_comparison(
        sessions,
        lstm_epochs=12,
        transformer_epochs=30,
        top_k=2,
        seed=42,
        tracker=tracker,
    )

    names = {report.name for report in result.reports}
    assert names == {"LSTM", "Transformer", "IsolationForest", "Ensemble"}

    # The tracker received a run per model, each with quality metrics.
    assert {run_name for run_name, _ in tracker.runs} == names
    assert all("precision" in metrics for _, metrics in tracker.runs)

    ensemble = next(r for r in result.reports if r.name == "Ensemble")
    assert ensemble.metrics.recall >= 0.9
    assert ensemble.metrics.precision >= 0.9
    assert ensemble.metrics.roc_auc >= 0.9

    # Operational metrics are populated and sane.
    for report in result.reports:
        assert report.throughput_per_sec > 0
        assert report.alerts_per_10k >= 0
        assert report.latency_ms_p95 >= report.latency_ms_p50

    table = result.as_table()
    assert "Model" in table and "Ensemble" in table
    assert result.best_by_f1().name in names


async def test_calibration_on_fixture(hdfs_log_path: Path, hdfs_label_path: Path) -> None:
    sessions = await _sessions(hdfs_log_path, hdfs_label_path)
    calibration = run_calibration(sessions, lstm_epochs=12, top_k=2, seed=42)

    assert calibration.after.recall == 1.0
    assert calibration.after.f1 >= 0.9
    assert 0.0 <= calibration.seq_weight <= 1.0
    # The chosen threshold is a real operating point in [0, 1].
    assert 0.0 <= calibration.threshold <= 1.0
