"""Unit test for the no-op experiment tracker."""

from __future__ import annotations

from nexguard.domain.ports import ExperimentTracker
from nexguard.infrastructure.tracking.null_tracker import NullExperimentTracker


def test_null_tracker_satisfies_port_and_noops() -> None:
    tracker = NullExperimentTracker()
    assert isinstance(tracker, ExperimentTracker)
    # Does nothing and raises nothing.
    tracker.log_run(run_name="r", params={"a": 1}, metrics={"precision": 0.9})
