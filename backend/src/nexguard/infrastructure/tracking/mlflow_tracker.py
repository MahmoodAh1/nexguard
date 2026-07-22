"""MLflow experiment tracker.

Implements the :class:`~nexguard.domain.ports.ExperimentTracker` port. Kept out of
the serving path — MLflow is an optional ``mlflow`` extra; import this module only
when tracking is enabled (the offline ``ml/`` runner does). NaN metrics (e.g.
ROC-AUC on a single-class split) are skipped so a run always records cleanly.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path

import mlflow


class MlflowExperimentTracker:
    """Records runs to an MLflow tracking backend (local file store by default)."""

    def __init__(self, *, experiment: str = "nexguard", tracking_uri: str | None = None) -> None:
        if tracking_uri is not None:
            mlflow.set_tracking_uri(tracking_uri)
        mlflow.set_experiment(experiment)

    def log_run(
        self,
        *,
        run_name: str,
        params: Mapping[str, object],
        metrics: Mapping[str, float],
        tags: Mapping[str, str] | None = None,
        artifacts: Sequence[Path] = (),
    ) -> None:
        with mlflow.start_run(run_name=run_name):
            if tags:
                mlflow.set_tags(dict(tags))
            mlflow.log_params(dict(params))
            mlflow.log_metrics(
                {key: float(value) for key, value in metrics.items() if not math.isnan(value)}
            )
            for artifact in artifacts:
                if Path(artifact).exists():
                    mlflow.log_artifact(str(artifact))
