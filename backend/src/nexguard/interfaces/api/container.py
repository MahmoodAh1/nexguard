"""Composition root.

The single place where concrete adapters are wired to domain ports (ADR-0001).
Nothing else in the system constructs infrastructure directly; routers receive
fully-assembled use cases from here via FastAPI dependencies. Repositories are
built per request-scoped session; the rest are process-singletons.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from nexguard.application.use_cases.auth import Authenticate, CreateUser
from nexguard.application.use_cases.detect_anomalies import DetectAnomalies
from nexguard.application.use_cases.feedback import Recalibrate, SubmitFeedback
from nexguard.application.use_cases.generate_report import GenerateReport
from nexguard.config.runtime import RuntimeConfig
from nexguard.config.settings import Settings
from nexguard.domain.ports import EventBus, LLMProvider, PasswordHasher, TokenService
from nexguard.infrastructure.bus.memory_bus import InMemoryEventBus
from nexguard.infrastructure.bus.redis_bus import RedisEventBus
from nexguard.infrastructure.db.repositories import (
    SqlAlchemyAlertRepository,
    SqlAlchemyAuditLog,
    SqlAlchemyCalibrationRepository,
    SqlAlchemyFeedbackRepository,
    SqlAlchemyLogRepository,
    SqlAlchemyReportRepository,
    SqlAlchemyTemplateRepository,
    SqlAlchemyUserRepository,
)
from nexguard.infrastructure.db.session import Database
from nexguard.infrastructure.detection.ensemble import WeightedEnsemble
from nexguard.infrastructure.detection.explain import Explainer
from nexguard.infrastructure.detection.sequence_lstm import LstmSequenceDetector
from nexguard.infrastructure.detection.statistical_iforest import (
    IsolationForestDetector,
)
from nexguard.infrastructure.llm.ollama_provider import OllamaLLMProvider
from nexguard.infrastructure.llm.stub_provider import StubLLMProvider
from nexguard.infrastructure.llm.verifier import EvidenceVerifier
from nexguard.observability.logging import get_logger
from nexguard.security.hashing import Argon2PasswordHasher
from nexguard.security.jwt import JwtTokenService

_LSTM_ARTIFACT = "lstm.pt"
_IFOREST_ARTIFACT = "iforest.joblib"

logger = get_logger("nexguard.container")


@dataclass(frozen=True)
class DetectorBundle:
    """The trained detection stack, loaded from artifacts.

    The ensemble is built per detection from the mutable RuntimeConfig, so
    recalibration / config changes take effect without reloading models.
    """

    sequence: LstmSequenceDetector
    statistical: IsolationForestDetector
    explainer: Explainer


class Container:
    """Application composition root."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.database_url)
        self.event_bus: EventBus = _build_event_bus(settings)
        self.hasher: PasswordHasher = Argon2PasswordHasher()
        self.tokens: TokenService = JwtTokenService(
            secret=settings.jwt_secret.get_secret_value(),
            algorithm=settings.jwt_algorithm,
            access_ttl_seconds=settings.access_token_ttl_seconds,
            refresh_ttl_seconds=settings.refresh_token_ttl_seconds,
        )
        self.llm: LLMProvider = _build_llm(settings)
        self.verifier = EvidenceVerifier()
        self.runtime = RuntimeConfig.from_settings(settings)
        self._detectors: DetectorBundle | None = None

    # ── lifecycle ──
    async def startup(self) -> None:
        if not self.settings.is_production:
            # Dev/test convenience; production schema is managed by Alembic.
            await self.database.create_all()
        self.load_detectors()

    async def shutdown(self) -> None:
        await self.database.dispose()
        if isinstance(self.event_bus, RedisEventBus):
            await self.event_bus.close()

    def load_detectors(self) -> DetectorBundle | None:
        directory = Path(self.settings.model_artifact_dir)
        lstm_path = directory / _LSTM_ARTIFACT
        iforest_path = directory / _IFOREST_ARTIFACT
        if not (lstm_path.exists() and iforest_path.exists()):
            logger.info("detectors_not_loaded", artifact_dir=str(directory))
            return None
        self._detectors = DetectorBundle(
            sequence=LstmSequenceDetector.load(lstm_path),
            statistical=IsolationForestDetector.load(iforest_path),
            explainer=Explainer(),
        )
        logger.info("detectors_loaded", artifact_dir=str(directory))
        return self._detectors

    @property
    def detectors(self) -> DetectorBundle | None:
        return self._detectors

    @property
    def model_name(self) -> str:
        return getattr(self.llm, "name", "unknown")

    # ── per-session repositories ──
    def users(self, session: AsyncSession) -> SqlAlchemyUserRepository:
        return SqlAlchemyUserRepository(session)

    def alerts(self, session: AsyncSession) -> SqlAlchemyAlertRepository:
        return SqlAlchemyAlertRepository(session)

    def logs(self, session: AsyncSession) -> SqlAlchemyLogRepository:
        return SqlAlchemyLogRepository(session)

    def reports(self, session: AsyncSession) -> SqlAlchemyReportRepository:
        return SqlAlchemyReportRepository(session)

    def audit(self, session: AsyncSession) -> SqlAlchemyAuditLog:
        return SqlAlchemyAuditLog(session)

    def feedback(self, session: AsyncSession) -> SqlAlchemyFeedbackRepository:
        return SqlAlchemyFeedbackRepository(session)

    def calibration(self, session: AsyncSession) -> SqlAlchemyCalibrationRepository:
        return SqlAlchemyCalibrationRepository(session)

    def templates(self, session: AsyncSession) -> SqlAlchemyTemplateRepository:
        return SqlAlchemyTemplateRepository(session)

    # ── use cases ──
    def authenticate(self, session: AsyncSession) -> Authenticate:
        return Authenticate(self.users(session), self.hasher, self.tokens)

    def submit_feedback(self, session: AsyncSession) -> SubmitFeedback:
        return SubmitFeedback(self.feedback(session), self.alerts(session))

    def recalibrate(self, session: AsyncSession) -> Recalibrate:
        return Recalibrate(
            self.feedback(session),
            self.alerts(session),
            self.calibration(session),
            self.runtime,
        )

    def create_user(self, session: AsyncSession) -> CreateUser:
        return CreateUser(self.users(session), self.hasher)

    def generate_report(self, session: AsyncSession) -> GenerateReport:
        return GenerateReport(
            llm=self.llm,
            verifier=self.verifier,
            alert_repo=self.alerts(session),
            report_repo=self.reports(session),
            log_repo=self.logs(session),
            model_name=self.model_name,
            event_bus=self.event_bus,
        )

    def detect_anomalies(self, session: AsyncSession) -> DetectAnomalies | None:
        if self._detectors is None:
            return None
        return DetectAnomalies(
            sequence_detector=self._detectors.sequence,
            statistical_detector=self._detectors.statistical,
            ensemble=WeightedEnsemble(
                seq_weight=self.runtime.seq_weight,
                stat_weight=self.runtime.stat_weight,
                threshold=self.runtime.threshold,
            ),
            explainer=self._detectors.explainer,
            alert_repo=self.alerts(session),
            event_bus=self.event_bus,
        )


def _build_event_bus(settings: Settings) -> EventBus:
    if settings.event_bus == "redis":
        return RedisEventBus(settings.redis_url)
    return InMemoryEventBus()


def _build_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaLLMProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout=settings.llm_timeout_seconds,
        )
    return StubLLMProvider()
