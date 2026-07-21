"""Fixtures for integration tests that exercise real adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from nexguard.infrastructure.db.session import Database

_FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def hdfs_log_path() -> Path:
    return _FIXTURES / "hdfs" / "hdfs_sample.log"


@pytest.fixture
def hdfs_label_path() -> Path:
    return _FIXTURES / "hdfs" / "anomaly_label.csv"


@pytest.fixture
async def database(tmp_path: Path) -> AsyncIterator[Database]:
    """A fresh file-backed SQLite database with the schema created."""
    url = f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
    db = Database(url)
    await db.create_all()
    try:
        yield db
    finally:
        await db.dispose()
