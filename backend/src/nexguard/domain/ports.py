"""Ports — the interfaces the domain defines and adapters implement.

These Protocols are the seams of the system. The application layer depends only
on them; ``infrastructure`` provides concrete adapters, wired in the composition
root. Structural typing (``Protocol``) means an adapter needs no explicit
inheritance — it simply has to match the shape.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Protocol, TypeVar, runtime_checkable
from uuid import UUID

from pydantic import BaseModel

from nexguard.domain.auth import Claims, TokenPair
from nexguard.domain.detection import (
    EnsembleVerdict,
    RawSession,
    SequenceVerdict,
    StatisticalVerdict,
    TemplateMatch,
)
from nexguard.domain.entities import (
    Alert,
    Feedback,
    IncidentReport,
    Session,
    Template,
    User,
)
from nexguard.domain.value_objects import CountVector, EventId
from nexguard.domain.verification import EvidenceIndex, VerificationResult

TModel = TypeVar("TModel", bound=BaseModel)


# ─────────────────────────── Persistence ports ───────────────────────────
@runtime_checkable
class LogRepository(Protocol):
    async def add_session(self, session: Session) -> Session: ...
    async def get_session(self, session_id: UUID) -> Session | None: ...
    async def get_session_by_external_id(
        self, dataset: str, external_id: str
    ) -> Session | None: ...
    async def list_sessions(self, *, limit: int = 100, offset: int = 0) -> list[Session]: ...


@runtime_checkable
class AlertRepository(Protocol):
    async def add(self, alert: Alert) -> Alert: ...
    async def get(self, alert_id: UUID) -> Alert | None: ...
    async def update(self, alert: Alert) -> Alert: ...
    async def list(
        self,
        *,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Alert]: ...


@runtime_checkable
class ReportRepository(Protocol):
    async def add(self, report: IncidentReport) -> IncidentReport: ...
    async def get_by_alert(self, alert_id: UUID) -> IncidentReport | None: ...


@runtime_checkable
class UserRepository(Protocol):
    async def add(self, user: User) -> User: ...
    async def get(self, user_id: UUID) -> User | None: ...
    async def by_email(self, email: str) -> User | None: ...


@runtime_checkable
class FeedbackRepository(Protocol):
    async def add(self, feedback: Feedback) -> Feedback: ...
    async def list_for_alert(self, alert_id: UUID) -> list[Feedback]: ...


@runtime_checkable
class TemplateRepository(Protocol):
    async def upsert_many(self, templates: Sequence[Template]) -> None: ...
    async def all(self) -> list[Template]: ...


@runtime_checkable
class AuditLog(Protocol):
    async def record(
        self,
        *,
        actor_id: UUID | None,
        action: str,
        resource: str,
        ip: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None: ...


# ─────────────────────────── Detection ports ───────────────────────────
@runtime_checkable
class TemplateMiner(Protocol):
    def mine(self, line: str) -> TemplateMatch: ...
    def vocabulary(self) -> list[Template]: ...


@runtime_checkable
class SequenceDetector(Protocol):
    def score(self, sequence: Sequence[EventId]) -> SequenceVerdict: ...


@runtime_checkable
class StatisticalDetector(Protocol):
    def score(self, counts: CountVector) -> StatisticalVerdict: ...


@runtime_checkable
class Ensemble(Protocol):
    def combine(
        self, sequence: SequenceVerdict, statistical: StatisticalVerdict
    ) -> EnsembleVerdict: ...


# ─────────────────────────── LLM triage ports ───────────────────────────
@runtime_checkable
class LLMProvider(Protocol):
    async def complete_json(self, prompt: str, schema: type[TModel]) -> TModel: ...


@runtime_checkable
class ReportVerifier(Protocol):
    def verify(
        self, report: IncidentReport, evidence_index: EvidenceIndex
    ) -> VerificationResult: ...


# ─────────────────────────── Infrastructure ports ───────────────────────────
@runtime_checkable
class EventBus(Protocol):
    async def publish(self, event: object) -> None: ...
    def subscribe(self, topic: str) -> AsyncIterator[dict[str, object]]: ...


@runtime_checkable
class DatasetSource(Protocol):
    def iter_sessions(self) -> Iterator[RawSession]: ...


@runtime_checkable
class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, password_hash: str) -> bool: ...


@runtime_checkable
class TokenService(Protocol):
    def issue(self, user: User) -> TokenPair: ...
    def decode(self, token: str) -> Claims: ...


@runtime_checkable
class ExperimentTracker(Protocol):
    """Records an ML experiment run (datasets, params, metrics, artifacts).

    Abstracts MLflow so the evaluation harness never imports it directly; a
    no-op adapter keeps offline runs working when tracking is disabled.
    """

    def log_run(
        self,
        *,
        run_name: str,
        params: Mapping[str, object],
        metrics: Mapping[str, float],
        tags: Mapping[str, str] | None = None,
        artifacts: Sequence[Path] = (),
    ) -> None: ...
