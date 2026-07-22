"""No-op experiment tracker — the default when tracking is disabled."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path


class NullExperimentTracker:
    """Implements the ExperimentTracker port and does nothing."""

    def log_run(
        self,
        *,
        run_name: str,
        params: Mapping[str, object],
        metrics: Mapping[str, float],
        tags: Mapping[str, str] | None = None,
        artifacts: Sequence[Path] = (),
    ) -> None:
        return None
