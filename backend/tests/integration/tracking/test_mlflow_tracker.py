"""Integration test for the MLflow tracker.

Skipped unless the optional ``mlflow`` extra is installed (it is not part of the
default/CI environment). When present, it logs a run to a local file store and
reads it back to prove datasets/params/metrics are recorded and NaN is skipped.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

mlflow = pytest.importorskip("mlflow")

from nexguard.infrastructure.tracking.mlflow_tracker import (  # noqa: E402
    MlflowExperimentTracker,
)

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_mlflow_tracker_records_a_run(tmp_path: Path) -> None:
    tracking_uri = (tmp_path / "mlruns").as_uri()
    tracker = MlflowExperimentTracker(experiment="nexguard-test", tracking_uri=tracking_uri)

    tracker.log_run(
        run_name="LSTM",
        params={"model": "LSTM", "dataset": "hdfs", "threshold": 0.5},
        metrics={"precision": 1.0, "recall": 1.0, "roc_auc": math.nan},
        tags={"phase": "test"},
    )

    client = mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)
    experiment = client.get_experiment_by_name("nexguard-test")
    assert experiment is not None

    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 1
    run = runs[0]
    assert run.data.params["model"] == "LSTM"
    assert run.data.metrics["precision"] == 1.0
    assert "roc_auc" not in run.data.metrics  # NaN was skipped
