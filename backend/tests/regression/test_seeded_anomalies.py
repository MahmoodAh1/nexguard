"""Seeded anomaly regression test.

Pins the end-to-end detection behavior on the known-labeled HDFS fixture: every
seeded anomalous block must be flagged (recall) and no normal block may be
(precision). Because the pipeline is fully seeded and deterministic, this catches
any silent regression in parsing, training, scoring, or the ensemble.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from nexguard.config.settings import Settings
from nexguard.interfaces.api.container import Container
from nexguard.interfaces.bootstrap import seed_demo

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "hdfs"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'reg.db').as_posix()}",
        model_artifact_dir=str(tmp_path / "artifacts"),
        event_bus="memory",
        llm_provider="stub",
        jwt_secret=SecretStr("regression-secret-value-1234567890abcd"),
    )


async def test_seeded_anomalies_are_all_flagged_with_no_false_positives(
    tmp_path: Path,
) -> None:
    container = Container(_settings(tmp_path))
    await container.startup()
    try:
        result = await seed_demo(
            container,
            log_path=str(_FIXTURES / "hdfs_sample.log"),
            label_path=str(_FIXTURES / "anomaly_label.csv"),
        )

        anomalies = [o for o in result.outcomes if o.is_anomaly is True]
        normals = [o for o in result.outcomes if o.is_anomaly is False]

        assert len(anomalies) == 10
        assert len(normals) == 60

        detected = sum(1 for o in anomalies if o.alerted)
        false_positives = sum(1 for o in normals if o.alerted)

        # Deterministic pipeline: perfect recall, zero false positives.
        assert detected == 10, f"recall regressed: {detected}/10"
        assert false_positives == 0, f"false positives appeared: {false_positives}/60"
        assert all(o.severity in {"high", "critical"} for o in anomalies if o.alerted)

        # Alerts were actually persisted.
        async with container.database.session() as session:
            persisted = await container.alerts(session).list(limit=500)
        assert len(persisted) == 10
    finally:
        await container.shutdown()


async def test_seed_is_idempotent_on_reruns(tmp_path: Path) -> None:
    """Re-running seed (as managed hosts do on every boot) must not duplicate."""
    container = Container(_settings(tmp_path))
    await container.startup()
    try:
        first = await seed_demo(
            container,
            log_path=str(_FIXTURES / "hdfs_sample.log"),
            label_path=str(_FIXTURES / "anomaly_label.csv"),
        )
        assert first.skipped is False
        assert first.alerts_created == 10

        # Second run detects the populated DB and short-circuits.
        second = await seed_demo(
            container,
            log_path=str(_FIXTURES / "hdfs_sample.log"),
            label_path=str(_FIXTURES / "anomaly_label.csv"),
        )
        assert second.skipped is True
        assert second.sessions_ingested == 0
        assert second.users_created == 0

        # No duplication: still exactly the 10 original alerts.
        async with container.database.session() as session:
            assert await container.alerts(session).total() == 10
    finally:
        await container.shutdown()
