"""Demo bootstrap: the full vertical slice as a reproducible pipeline.

Ingests the bundled HDFS fixture, trains both detectors on the *normal* sessions,
persists the model artifacts, scores every session to raise alerts, and creates
demo users. This is what ``nexguard seed`` runs and what the seeded-anomaly
regression test exercises end to end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from nexguard.application.use_cases.auth import CreateUser
from nexguard.application.use_cases.ingest_and_parse import IngestAndParse
from nexguard.domain.entities import Session, UserRole
from nexguard.domain.errors import ValidationError
from nexguard.domain.value_objects import CountVector
from nexguard.infrastructure.datasets.hdfs import HdfsDatasetSource
from nexguard.infrastructure.db.repositories import SqlAlchemyTemplateRepository
from nexguard.infrastructure.detection.sequence_lstm import LstmSequenceDetector
from nexguard.infrastructure.detection.statistical_iforest import (
    IsolationForestDetector,
)
from nexguard.infrastructure.parsing.drain3_miner import Drain3TemplateMiner
from nexguard.interfaces.api.container import Container
from nexguard.observability.logging import get_logger

logger = get_logger("nexguard.bootstrap")

_DEMO_USERS: tuple[tuple[str, str, UserRole], ...] = (
    ("admin@nexguard.local", "NexGuardAdmin!23", UserRole.ADMIN),
    ("analyst@nexguard.local", "NexGuardAnalyst!23", UserRole.ANALYST),
    ("viewer@nexguard.local", "NexGuardViewer!23", UserRole.VIEWER),
)

_LSTM_ARTIFACT = "lstm.pt"
_IFOREST_ARTIFACT = "iforest.joblib"


@dataclass(frozen=True)
class SeedOutcome:
    external_id: str
    is_anomaly: bool | None
    alerted: bool
    score: float | None
    severity: str | None


@dataclass
class SeedResult:
    users_created: int = 0
    sessions_ingested: int = 0
    alerts_created: int = 0
    outcomes: list[SeedOutcome] = field(default_factory=list)


async def seed_demo(
    container: Container,
    *,
    log_path: str | Path,
    label_path: str | Path | None,
    lstm_epochs: int = 15,
    top_k: int = 2,
    seed: int = 42,
    create_users: bool = True,
) -> SeedResult:
    result = SeedResult()

    # 1. Ingest + parse the fixture into persisted sessions.
    miner = Drain3TemplateMiner()
    async with container.database.session() as session:
        ingest = IngestAndParse(
            miner, container.logs(session), SqlAlchemyTemplateRepository(session)
        )
        sessions = await ingest.execute(
            HdfsDatasetSource(log_path, label_path).iter_sessions()
        )
    result.sessions_ingested = len(sessions)
    logger.info("seed_ingested", sessions=len(sessions))

    # 2. Train both detectors on NORMAL sessions only (semi-supervised).
    normal = [s for s in sessions if s.label is False] or sessions
    templates = {int(t.event_id): t.template for t in miner.vocabulary()}
    _train_and_save(
        container, normal, templates, lstm_epochs=lstm_epochs, top_k=top_k, seed=seed
    )
    container.load_detectors()
    logger.info("seed_trained", normal_sessions=len(normal), templates=len(templates))

    # 3. Score every session, raising alerts (and publishing events).
    async with container.database.session() as session:
        detect = container.detect_anomalies(session)
        assert detect is not None  # just trained + loaded
        for parsed in sessions:
            alert = await detect.execute(parsed)
            if alert is not None:
                result.alerts_created += 1
            result.outcomes.append(
                SeedOutcome(
                    external_id=parsed.external_id,
                    is_anomaly=parsed.label,
                    alerted=alert is not None,
                    score=round(alert.score.value, 4) if alert else None,
                    severity=alert.severity.value if alert else None,
                )
            )
    logger.info("seed_detected", alerts=result.alerts_created)

    # 4. Create demo users.
    if create_users:
        async with container.database.session() as session:
            creator = container.create_user(session)
            result.users_created = await _create_demo_users(creator)
    logger.info("seed_users", created=result.users_created)

    return result


def _train_and_save(
    container: Container,
    normal: list[Session],
    templates: dict[int, str],
    *,
    lstm_epochs: int,
    top_k: int,
    seed: int,
) -> None:
    sequence_detector = LstmSequenceDetector.fit(
        [s.event_id_sequence() for s in normal],
        epochs=lstm_epochs,
        top_k=top_k,
        seed=seed,
    )
    count_vectors = [
        CountVector.from_counts(s.event_counts(), tuple(s.event_counts().keys()))
        for s in normal
    ]
    statistical_detector = IsolationForestDetector.fit(
        count_vectors, templates=templates, seed=seed
    )

    directory = Path(container.settings.model_artifact_dir)
    sequence_detector.save(directory / _LSTM_ARTIFACT)
    statistical_detector.save(directory / _IFOREST_ARTIFACT)


async def _create_demo_users(creator: CreateUser) -> int:
    created = 0
    for email, password, role in _DEMO_USERS:
        try:
            await creator.execute(email=email, password=password, role=role)
            created += 1
        except ValidationError:
            # Already seeded — idempotent.
            continue
    return created
