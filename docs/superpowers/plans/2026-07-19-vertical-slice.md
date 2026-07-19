# NexGuard Vertical Slice — Implementation Plan

> **For agentic workers:** Implement task-by-task with TDD. Steps use checkbox
> (`- [ ]`) syntax. Executed inline in-session via superpowers:executing-plans.

**Goal:** One complete, real end-to-end path through every layer — ingest an HDFS
fixture → Drain3 parse → LSTM + IsolationForest → ensemble → explained alert →
Ollama report + verifier → FastAPI (auth/RBAC/WS) → one live Next.js page — with
tests at every layer and `docker compose up`.

**Architecture:** Clean Architecture / Ports & Adapters. `domain` (entities,
value objects, ports) ← `application` (use cases) ← `infrastructure` (adapters)
+ `interfaces` (FastAPI/WS/CLI, composition root). See `docs/architecture/`.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic v2, SQLAlchemy 2.0 async,
Alembic, PyTorch, scikit-learn, Drain3, Ollama, Redis, structlog, Argon2id, JWT,
pytest; Next.js 15 / React 19 / TS / Tailwind v4 / shadcn/ui / TanStack Query.

## Global Constraints
- Python **3.12+**; `mypy --strict` clean; `ruff` clean.
- No cloud APIs — LLM is **Ollama only**; a stub adapter satisfies CI.
- No `TODO` placeholders for core functionality.
- Every port has ≥2 adapters or an adapter + test double.
- Secrets via `pydantic-settings` from env; `.env` git-ignored.
- Every task ends green: tests written **and run**, then commit (Conventional Commits).
- Determinism: fixed seeds; CPU path stable for CI.

---

## File structure (Phase 1)

```
backend/
  pyproject.toml, uv.lock, ruff.toml, .env.example, alembic.ini
  src/nexguard/
    domain/
      value_objects.py    # EventId, Score, Severity, Confidence, TimeRange
      entities.py         # Template, LogEvent, Session, DetectionRun, Alert, IncidentReport, User, Feedback
      events.py           # DomainEvent, AlertCreated
      ports.py            # Protocols: repos, TemplateMiner, SequenceDetector, StatisticalDetector, Ensemble, Explainer, LLMProvider, ReportVerifier, EventBus, DatasetSource, PasswordHasher, TokenService
      errors.py           # domain error hierarchy
      report.py           # IncidentReportPayload (Pydantic) + MitreHypothesis, TimelineEntry
    application/
      dto.py
      use_cases/
        ingest_and_parse.py   # IngestAndParse: raw lines -> persisted sessions
        detect_anomalies.py   # DetectAnomalies: session -> Alert(+Evidence)
        generate_report.py     # GenerateReport: alert -> verified IncidentReport
        auth.py                # Authenticate, IssueTokens
    infrastructure/
      db/
        base.py, models.py, session.py, repositories.py, unit_of_work.py
      parsing/drain3_miner.py
      detection/
        sequence_lstm.py, statistical_iforest.py, ensemble.py, explain.py, artifacts.py
      llm/ollama_provider.py, stub_provider.py, verifier.py, prompts.py
      bus/memory_bus.py, redis_bus.py
      datasets/hdfs.py
    config/settings.py
    security/hashing.py, jwt.py, rbac.py
    observability/logging.py, metrics.py
    interfaces/
      api/app.py, container.py, deps.py, schemas.py, middleware.py, errors.py
      api/routers/health.py, auth.py, alerts.py, ws.py, metrics.py
      cli.py
    __main__.py
  migrations/ (alembic)
  tests/
    unit/ (domain + use cases with fakes)
    integration/ (adapters against real sqlite/drain3/torch/sklearn)
    api/ (httpx against app)
    regression/test_seeded_anomalies.py
    fixtures/hdfs_sample.log, hdfs_labels.csv, conftest.py
frontend/
  package.json, next.config.ts, tailwind, tsconfig, app/(auth)/login, app/(app)/dashboard,
  lib/api.ts, lib/ws.ts, lib/auth.ts, components/ui/*, components/alerts/*
docker/
  Dockerfile.backend, Dockerfile.frontend, docker-compose.yml
.github/workflows/ci.yml
.pre-commit-config.yaml
scripts/seed.py, scripts/download_data.py
```

---

## Task ordering (dependency-first)

### Task 1 — Backend scaffold & tooling
**Files:** `backend/pyproject.toml`, `ruff.toml`, `.env.example`, `src/nexguard/__init__.py`, `tests/conftest.py`
**Produces:** installable `nexguard` package; `pytest`, `ruff`, `mypy` runnable.
- [ ] pyproject with deps + tool config (ruff/mypy/pytest/coverage).
- [ ] `uv sync`; smoke test `test_package_imports`.
- [ ] Run `pytest -q` (1 passing), `ruff check`, `mypy`. Commit.

### Task 2 — Domain value objects
**Files:** `domain/value_objects.py`, `tests/unit/domain/test_value_objects.py`
**Produces:** `EventId(int)`, `Score(value: float 0..1)`, `Severity` enum + `from_score`, `Confidence`, `TimeRange`.
- [ ] Tests: Score rejects out-of-range; `Severity.from_score` band boundaries; TimeRange ordering.
- [ ] Implement frozen dataclasses / enums. Run tests. Commit.

### Task 3 — Domain entities, events, errors, report schema
**Files:** `domain/entities.py`, `events.py`, `errors.py`, `report.py`, tests.
**Interfaces produced (consumed everywhere):**
- `Template(event_id: EventId, template: str, ...)`, `LogEvent(...)`, `Session(external_id, dataset, events: list[LogEvent], label)` with `.event_id_sequence()` and `.count_vector(vocab)`.
- `Alert(id, session_id, score: Score, severity: Severity, status, evidence: Evidence, ...)`, `Evidence` (sequence/statistical/ensemble/provenance).
- `IncidentReportPayload` (Pydantic): summary, severity, confidence, timeline[], affected_components[], evidence_refs[], mitre_hypotheses[], investigation_steps[], containment_actions[]. `MitreHypothesis` requires `is_hypothesis=True`.
- [ ] Tests: Session sequence/count-vector correctness; report schema rejects a MITRE entry not marked hypothesis; Evidence round-trips to/from dict.
- [ ] Implement. Run. Commit.

### Task 4 — Ports (Protocols)
**Files:** `domain/ports.py`, `tests/unit/domain/test_ports_contract.py`
**Produces (the contracts all adapters/use-cases share):**
```python
class LogRepository(Protocol): async def add_session(self, s: Session) -> Session; async def get(self, id) -> Session | None
class AlertRepository(Protocol): async def add(self, a: Alert) -> Alert; async def list(self, ...) -> list[Alert]; async def get(self, id)
class ReportRepository(Protocol): async def add(self, r) -> IncidentReport; async def get_by_alert(self, alert_id)
class UserRepository(Protocol): async def by_email(self, email) -> User | None; async def add(self, u)
class TemplateMiner(Protocol): def mine(self, line: str) -> TemplateMatch; def vocabulary(self) -> dict[str,int]
class SequenceDetector(Protocol): def score(self, seq: list[EventId]) -> SequenceVerdict
class StatisticalDetector(Protocol): def score(self, counts: CountVector) -> StatisticalVerdict
class Ensemble(Protocol): def combine(self, s: SequenceVerdict, st: StatisticalVerdict) -> EnsembleVerdict
class LLMProvider(Protocol): async def complete_json(self, prompt: str, schema: type[T]) -> T
class ReportVerifier(Protocol): def verify(self, report, evidence: EvidenceIndex) -> VerificationResult
class EventBus(Protocol): async def publish(self, topic, event); def subscribe(self, topic) -> AsyncIterator
class DatasetSource(Protocol): def iter_sessions(self) -> Iterator[RawSession]
class PasswordHasher(Protocol): def hash(self, pw) -> str; def verify(self, pw, hash) -> bool
class TokenService(Protocol): def issue(self, user) -> TokenPair; def decode(self, token) -> Claims
```
- [ ] Contract test: a trivial fake implements each Protocol (structural typing check via `isinstance`/`mypy`). Commit.

### Task 5 — Config, logging, security primitives
**Files:** `config/settings.py`, `observability/logging.py`, `security/hashing.py`, `jwt.py`, `rbac.py`, tests.
**Produces:** `Settings` (env), `configure_logging()`, `Argon2Hasher` (impl PasswordHasher), `JwtTokenService` (impl TokenService), `require_role(...)`.
- [ ] Tests: hash≠plaintext & verify round-trip; JWT issue→decode round-trip, expired token rejected, tampered token rejected; RBAC allows/denies by role.
- [ ] Implement. Run. Commit.

### Task 6 — Persistence: models, repositories, UoW, migration
**Files:** `infrastructure/db/{base,models,session,repositories,unit_of_work}.py`, `migrations/`, tests.
**Produces:** SQLAlchemy 2.0 async models for all data-model tables; repo adapters implementing the repo ports; `create_all` for tests + Alembic initial revision.
- [ ] Integration tests (aiosqlite in-memory): add/get Session with events; add/list Alerts by severity; user by_email; report by alert.
- [ ] Implement. Run. Commit.

### Task 7 — Drain3 template miner adapter
**Files:** `infrastructure/parsing/drain3_miner.py`, tests.
**Produces:** `Drain3TemplateMiner` implementing `TemplateMiner`; stable `EventId` per template; persistable vocabulary.
- [ ] Integration tests: two lines differing only in a block id → same template/EventId; distinct message → distinct EventId; vocabulary round-trips.
- [ ] Implement (drain3 with persistence handler). Run. Commit.

### Task 8 — IngestAndParse use case
**Files:** `application/use_cases/ingest_and_parse.py`, tests (fakes).
**Produces:** `IngestAndParse(miner, repo).execute(dataset, lines, labels) -> list[Session]`; assembles sessions by `block_id` (HDFS regex), assigns EventIds, persists.
- [ ] Unit test with in-memory repo + real miner: HDFS sample lines → N sessions with correct event sequences & labels.
- [ ] Implement. Run. Commit.

### Task 9 — Statistical detector (Isolation Forest)
**Files:** `infrastructure/detection/statistical_iforest.py`, `artifacts.py`, tests.
**Produces:** `IsolationForestDetector` implementing `StatisticalDetector`; `.fit(count_vectors)`, `.score(counts) -> StatisticalVerdict(score, important_features)`; save/load artifact.
- [ ] Integration test: fit on normal count-vectors; an outlier session scores higher than a normal one; important_features non-empty; artifact save/load preserves scores.
- [ ] Implement (sklearn IsolationForest + per-feature attribution). Run. Commit.

### Task 10 — Sequence detector (PyTorch LSTM)
**Files:** `infrastructure/detection/sequence_lstm.py`, tests.
**Produces:** `LstmSequenceDetector` implementing `SequenceDetector`; embedding→LSTM→vocab head; `.fit(normal_sequences, epochs)`, `.score(seq) -> SequenceVerdict(anomaly_score, predicted_topk, actual_event, confidence, perplexity, suspicious_subsequence, surprising_steps)`; save/load.
- [ ] Integration test (tiny, seeded, CPU, few epochs): trained on a repeating-normal grammar, an out-of-grammar sequence yields ≥1 surprising step and higher anomaly_score than an in-grammar one; verdict fields populated.
- [ ] Implement. Run. Commit.

### Task 11 — Ensemble + Explainer
**Files:** `infrastructure/detection/ensemble.py`, `explain.py`, tests.
**Produces:** `WeightedEnsemble(weights, threshold)` implementing `Ensemble`; `Explainer.build(session, seq_v, stat_v, ens_v) -> Evidence`.
- [ ] Tests: weighted combination math; threshold→severity banding; both-high → higher than one-high; Evidence contains predicted-vs-actual, suspicious subsequence, top features.
- [ ] Implement. Run. Commit.

### Task 12 — DetectAnomalies use case
**Files:** `application/use_cases/detect_anomalies.py`, tests (fakes).
**Produces:** `DetectAnomalies(seq, stat, ensemble, explainer, alert_repo, bus).execute(session) -> Alert`; persists alert; publishes `AlertCreated`.
- [ ] Unit test with fakes: anomalous session → Alert persisted + event published; normal session below threshold → no alert (or benign status).
- [ ] Implement. Run. Commit.

### Task 13 — LLM triage: stub + Ollama providers, prompts, verifier
**Files:** `infrastructure/llm/{stub_provider,ollama_provider,prompts,verifier}.py`, tests.
**Produces:** `StubLLMProvider` & `OllamaLLMProvider` implementing `LLMProvider` (`complete_json` → Pydantic); `EvidenceIndex.from_session_alert(...)`; `EvidenceVerifier` implementing `ReportVerifier` — checks every citation (event/host/timestamp/component) exists; rejects otherwise; forces MITRE=hypothesis.
- [ ] Tests: stub returns schema-valid report; verifier accepts a grounded report; verifier **rejects** a report citing a non-existent host/timestamp/event; MITRE entries flagged hypothesis.
- [ ] Implement. Run. Commit.

### Task 14 — GenerateReport use case
**Files:** `application/use_cases/generate_report.py`, tests (fakes).
**Produces:** `GenerateReport(llm, verifier, alert_repo, report_repo).execute(alert_id) -> IncidentReport`; verified→persist accepted, else persist rejected+reason.
- [ ] Unit test: grounded stub → verified report persisted; ungrounded stub → rejected with reason.
- [ ] Implement. Run. Commit.

### Task 15 — Composition root + FastAPI app + middleware
**Files:** `interfaces/api/{container,app,deps,middleware,errors,schemas}.py`, tests.
**Produces:** `Container` wiring adapters→ports from `Settings`; `create_app()`; middleware (correlation id, security headers, rate limit, RFC-9457 errors); `Depends` providers incl. `current_user`, `require_role`.
- [ ] API test: app boots; `/health` 200; security headers present; unknown route → problem+json.
- [ ] Implement. Run. Commit.

### Task 16 — Auth router + Alerts router + WebSocket
**Files:** `interfaces/api/routers/{auth,alerts,ws,metrics}.py`, `use_cases/auth.py`, tests.
**Produces:** `POST /auth/login`→JWT; `GET /alerts`, `GET /alerts/{id}`, `POST /alerts/{id}/report`, `GET /alerts/{id}/report` (RBAC + audit); `WS /ws/alerts` bridging `EventBus` `alert.created`→client.
- [ ] API tests: login issues token; unauthed alert list → 401; authed → 200; report endpoint returns verified report; WS receives a published alert event.
- [ ] Implement. Run. Commit.

### Task 17 — Seed script + seeded anomaly regression test + CLI
**Files:** `scripts/seed.py`, `interfaces/cli.py`, `tests/regression/test_seeded_anomalies.py`, fixtures.
**Produces:** CLI/seed that runs ingest→train→detect on the fixture and creates an admin user; regression test pinning verdicts on known anomalous/normal blocks.
- [ ] Regression test: seeded anomalous block flagged (severity ≥ high), seeded normal block not flagged. Run. Commit.

### Task 18 — Frontend scaffold + login + live dashboard
**Files:** `frontend/*`, `app/(auth)/login`, `app/(app)/dashboard`, `lib/{api,ws,auth}.ts`, components.
**Produces:** Next.js app; login posts to API, stores JWT; dashboard lists alerts (TanStack Query) + subscribes to `WS /ws/alerts` for live inserts; report drawer; premium dark theme.
- [ ] Component/e2e-lite test (Vitest/Testing Library): login form submits; dashboard renders an alert row from mocked data; typecheck passes.
- [ ] Implement. Run. Commit.

### Task 19 — Docker, Compose, CI, pre-commit
**Files:** `docker/Dockerfile.backend`, `Dockerfile.frontend`, `docker-compose.yml`, `.github/workflows/ci.yml`, `.pre-commit-config.yaml`.
**Produces:** `docker compose up` → postgres + redis + api + worker + frontend (+ ollama optional); CI runs ruff/mypy/pytest + eslint/tsc/vitest; pre-commit hooks.
- [ ] Build backend image; `docker compose config` valid; CI workflow lints+tests. Commit.

### Task 20 — Gate 1 wrap-up
- [ ] Full suite green (`pytest`, frontend tests). Update README + build-plan checkboxes. Commit. Present Gate 1.

---

## Self-review
- **Spec coverage (slice scope):** ingestion ✅(T8) parsing/template-mining ✅(T7)
  sequence detection ✅(T10) statistical ✅(T9) ensemble ✅(T11) explainable alerts
  ✅(T11-12) LLM report ✅(T13-14) verification ✅(T13) auth/RBAC/audit ✅(T5,15,16)
  realtime WS ✅(T16,18) dashboard ✅(T18) tests every layer ✅ seeded regression
  ✅(T17) docker/CI ✅(T19). Feedback loop, evaluation harness, MLflow, remaining
  7 pages, BGL/CICIDS → **Phase 2/3** (by design, not gaps).
- **Placeholders:** none — each task has concrete tests + interfaces.
- **Type consistency:** port signatures in T4 are the shared contract; use cases
  (T8,12,14) and adapters (T6,7,9,10,11,13) consume exactly those names.
