# NexGuard — System Architecture

> **AI-Powered Security Operations Platform**
> _Detect Faster. Investigate Smarter. Respond with Confidence._

This document is the architectural source of truth for NexGuard. It describes the
system's purpose, its guiding principles, the module topology, the runtime
data-flow, the technology choices (each justified), and the deployment model.
Deep-dives live in sibling documents:

| Document | Scope |
|----------|-------|
| [`detection-pipeline.md`](./detection-pipeline.md) | ML/DL/statistical detection, ensemble, explainability, evaluation |
| [`data-model.md`](./data-model.md) | Domain entities, persistence schema, migrations |
| [`build-plan.md`](./build-plan.md) | Phased build order and the checkpoint gates |
| [`adr/`](./adr) | Architecture Decision Records — the _why_ behind irreversible choices |

---

## 1. Product thesis

SOC analysts drown in alerts. The median enterprise SOC processes tens of
thousands of events per day, and the dominant operational cost is **analyst
attention wasted on false positives** ("alert fatigue"). NexGuard attacks this
with a layered detection stack that is **explainable by construction**, an
**LLM triage copilot** that drafts analyst-ready incident reports, and a
**verification layer** that refuses to let the copilot fabricate evidence. A
**feedback loop** lets analysts correct the system, and recalibration turns
those corrections into measurable precision/recall gains.

Everything runs **locally and privacy-preserving** — no security telemetry
leaves the operator's infrastructure, and the LLM is a local Ollama model, never
a cloud API. This is a hard requirement for the target buyer (a SOC handling
sensitive logs) and a first-class architectural constraint.

## 2. Design principles

1. **Clean Architecture / Ports & Adapters.** The domain and application layers
   know nothing about FastAPI, SQLAlchemy, PyTorch, or Ollama. Every external
   concern is a *port* (an interface) with a swappable *adapter*. This is what
   lets us run the same detection use case against a Postgres repository in
   production and an in-memory one in a unit test, or swap a real Ollama model
   for a deterministic stub in CI.
2. **Dependency inversion + explicit composition root.** High-level policy
   depends on abstractions; concrete wiring happens in one place (the container).
   No hidden global singletons, no service-locator anti-pattern.
3. **Typed contracts end-to-end.** Pydantic v2 on the wire and for LLM outputs,
   SQLAlchemy 2.0 typed models in the store, `mypy --strict` on Python, and
   `zod` schemas mirrored in TypeScript on the frontend. An AI call that feeds
   application logic is *always* schema-validated — never free text parsed with
   regex.
4. **Security is not a layer you add later.** AuthN/AuthZ, audit logging, input
   validation, rate limiting, and secure secrets are designed into the request
   path from the first slice.
5. **Observability as a feature.** Every detection decision, tool call, and LLM
   generation is logged as structured data and surfaced in the product itself
   (Live Monitoring, Detection Analytics), because in a SOC the *auditability of
   the tooling* is part of the product.
6. **No placeholders for core functionality.** Where a real model, a real
   parser, or a real verifier is required, we build it. Graceful degradation
   (e.g. a stub LLM when Ollama is absent) is an explicit, documented adapter —
   not a `TODO`.
7. **YAGNI on infrastructure.** We reach for Kafka/K8s-scale machinery only
   behind an interface, defaulting to the simplest thing that is correct and
   locally runnable (Redis, Compose). The abstraction preserves the upgrade path
   without paying its cost up front.

## 3. C4 — Level 1: System context

```
                         ┌────────────────────────────────────────────┐
                         │                 NexGuard                     │
   ┌───────────┐  logs   │  ┌───────────┐   ┌───────────────────────┐  │
   │  Log       │───────▶│  │ Ingestion │──▶│  Detection & Triage   │  │
   │  Sources   │        │  │ + Parsing │   │  (ML/DL/LLM pipeline) │  │
   │ (HDFS/BGL/ │        │  └───────────┘   └───────────┬───────────┘  │
   │  CICIDS)   │        │                              │ alerts,      │
   └───────────┘         │                              │ reports      │
                         │                        ┌─────▼──────┐       │
   ┌───────────┐  REST/  │                        │  Platform  │       │
   │  SOC       │◀──WS───▶│                        │  API + WS  │       │
   │  Analyst   │  browser│                        └─────┬──────┘       │
   └───────────┘         └──────────────────────────────┼──────────────┘
                                                         │
                              ┌──────────────────────────┼───────────────┐
                              ▼             ▼             ▼               ▼
                          Postgres        Redis         MLflow         Ollama
                        (system of      (event bus,   (experiment    (local LLM,
                          record)       cache, RL)     tracking)      no cloud)
```

## 4. C4 — Level 2: Containers

| Container | Tech | Responsibility |
|-----------|------|----------------|
| **web** | Next.js 15 / React 19 / TS / Tailwind v4 / shadcn/ui | Enterprise SOC console; 8 pages; live via WebSocket |
| **api** | FastAPI / Python 3.12 / Uvicorn | REST + WebSocket, auth, RBAC, use-case orchestration |
| **worker** | Python / asyncio | Long-running stream: ingest → parse → detect → alert → publish |
| **postgres** | PostgreSQL 16 (SQLite in dev/tests) | System of record: logs, sessions, alerts, reports, feedback, audit |
| **redis** | Redis 7 | Event bus (pub/sub), work queues, rate-limit buckets, hot cache |
| **mlflow** | MLflow | Experiment tracking, model registry, artifacts |
| **ollama** | Ollama | Local LLM inference for triage report generation |

The `api` and `worker` are two entry points over **one shared Python package**
(`nexguard`), so domain logic is written once and reused. See §6.

## 5. Clean Architecture layers (Python)

Dependencies point **inward only**. Nothing in `domain` imports from
`infrastructure`; the arrow of knowledge always flows toward the domain.

```
┌──────────────────────────────────────────────────────────────────────┐
│  interfaces/   FastAPI routers, WS handlers, CLI, request/response     │
│                schemas, the composition root (DI container)            │
│    │  depends on ▼                                                     │
│  application/  Use cases (IngestLogs, DetectAnomalies, GenerateReport, │
│                SubmitFeedback, Calibrate…), DTOs, orchestration        │
│    │  depends on ▼                                                     │
│  domain/       Entities (Session, LogEvent, Template, Alert,           │
│                IncidentReport…), value objects (Score, Severity,       │
│                EventId), domain services, and PORTS (interfaces):      │
│                LogRepository, TemplateMiner, SequenceDetector,         │
│                StatisticalDetector, Ensemble, LLMProvider, Verifier,   │
│                EventBus, ExperimentTracker …                           │
│    ▲  implemented by                                                   │
│  infrastructure/  Adapters: SQLAlchemy repos, Drain3 miner, PyTorch    │
│                LSTM/Transformer, sklearn IsolationForest, Ollama       │
│                client, Redis bus, MLflow tracker, Argon2 hasher        │
└──────────────────────────────────────────────────────────────────────┘
        config/   observability/   security/     (cross-cutting, injected)
```

**Why this shape.** The reviewer test for good boundaries is: *can you change an
adapter's internals without touching a consumer?* Here, replacing the LSTM with
a Transformer, or Postgres with SQLite, or Ollama with a stub, changes exactly
one adapter and zero use cases. That is the property that makes the system
testable, and it is the property that a demo-grade codebase lacks.

### Ports (the domain's contract with the world)

```python
class TemplateMiner(Protocol):
    def mine(self, line: str) -> TemplateMatch: ...

class SequenceDetector(Protocol):
    def score(self, sequence: EventSequence) -> SequenceVerdict: ...

class StatisticalDetector(Protocol):
    def score(self, features: SessionFeatures) -> StatisticalVerdict: ...

class LLMProvider(Protocol):
    async def complete_json(self, prompt: Prompt, schema: type[T]) -> T: ...

class ReportVerifier(Protocol):
    def verify(self, report: IncidentReport, evidence: EvidenceIndex) -> VerificationResult: ...

class EventBus(Protocol):
    async def publish(self, topic: str, event: DomainEvent) -> None: ...
    def subscribe(self, topic: str) -> AsyncIterator[DomainEvent]: ...
```

## 6. Repository topology

The spec's top-level layout is honored, with a clean split between **online
serving** (the running platform) and **offline MLOps** (training/evaluation):

```
NexGuard/
├── backend/            # The nexguard Python package (installable) + FastAPI app
│   └── src/nexguard/
│       ├── domain/         # entities, value objects, ports — zero framework deps
│       ├── application/     # use cases, DTOs
│       ├── infrastructure/  # adapters (db, parsing, detection, llm, bus, mlflow)
│       ├── interfaces/      # FastAPI routers, WS, schemas, DI container, CLI
│       ├── config/          # pydantic-settings, env-based configuration
│       ├── observability/   # structured logging, metrics, tracing
│       └── security/        # jwt, rbac, hashing, audit
├── ml/                 # OFFLINE MLOps: training pipelines, evaluation harness,
│                       #   MLflow projects, model cards, notebooks
├── services/           # Standalone workers (stream ingestion/detection consumer)
├── frontend/           # Next.js app (App Router)
├── infrastructure/     # IaC-adjacent config: nginx, prometheus, grafana, env
├── docker/             # Dockerfiles + docker-compose stacks
├── scripts/            # data download, seeding, model bootstrap, dev helpers
├── tests/              # cross-cutting integration/e2e (unit tests live beside code)
└── docs/               # architecture, ADRs, specs, runbooks
```

**Why one package, multiple entry points** (vs. many small distributions): the
`api` and the `worker` share the same domain and use cases. Splitting them into
separate installable packages would force premature interface freezing and
duplicate the composition root. A single `nexguard` distribution with distinct
entry points (`nexguard.interfaces.api:app`, `nexguard.services.stream:main`)
gives us reuse now and a clean extraction path later if the worker ever needs to
scale independently. `ml/` is intentionally separate: offline training has
different dependencies (heavier, GPU-optional) and a different lifecycle than the
serving path, and we don't want training deps in the API image.

## 7. Runtime data flow (the vertical slice)

```
 raw log line
     │
     ▼  IngestLogs use case
 ┌─────────────┐   Drain3    ┌──────────────┐  assemble by   ┌───────────┐
 │ LogEvent    │────────────▶│ Template +   │──block_id────▶ │  Session  │
 │ (persisted) │  mine()     │ EventId      │                │ (sequence)│
 └─────────────┘             └──────────────┘                └─────┬─────┘
                                                                   │ DetectAnomalies
                    ┌──────────────────────────────────────────────┤
                    ▼                                               ▼
          ┌───────────────────┐                        ┌───────────────────────┐
          │ SequenceDetector  │  next-event prediction │ StatisticalDetector   │
          │ (LSTM/Transformer)│  perplexity, top-k     │ (IsolationForest)     │
          └─────────┬─────────┘                        └───────────┬───────────┘
                    │ SequenceVerdict                              │ StatisticalVerdict
                    └───────────────────┬──────────────────────────┘
                                        ▼  Ensemble (weighted, calibrated)
                                 ┌──────────────┐
                                 │ Score +      │  Explainability assembles evidence:
                                 │ Severity     │  predicted vs actual, confidence,
                                 └──────┬───────┘  suspicious subsequence, top features
                                        ▼
                                 ┌──────────────┐  publish(alert.created)
                                 │    Alert     │───────────────────────────▶ EventBus ──▶ WS ──▶ UI
                                 │ (persisted)  │
                                 └──────┬───────┘
                                        ▼  GenerateReport (on demand / auto for high sev)
                          ┌──────────────────────────┐
                          │  LLMProvider (Ollama)     │  Pydantic-structured output
                          │  → IncidentReport draft   │
                          └────────────┬─────────────┘
                                       ▼  ReportVerifier
                          ┌──────────────────────────┐   citations/timestamps/hosts/events
                          │  VerificationResult       │   must exist in EvidenceIndex,
                          │  accept │ reject          │   else REJECT (no fabrication)
                          └──────────────────────────┘
```

## 8. Technology choices — and why

| Concern | Choice | Justification |
|---------|--------|---------------|
| Language (services) | **Python 3.12** | Ecosystem for ML/DL/LLM; typing maturity |
| Env/deps | **uv** | Fast, reproducible lockfile; single tool for venv + deps |
| Web framework | **FastAPI** | Async, Pydantic-native, first-class WebSockets, OpenAPI |
| Validation | **Pydantic v2** | One schema system for API, config, and LLM output contracts |
| ORM / migrations | **SQLAlchemy 2.0 (async) + Alembic** | Typed models, async I/O, versioned schema |
| DB | **SQLite (dev) → PostgreSQL (prod)** | Zero-setup dev; production concurrency + JSONB |
| Sequence model | **PyTorch (LSTM + Transformer encoder)** | DeepLog-style next-event prediction; both variants for comparison |
| Statistical model | **scikit-learn IsolationForest** | Unsupervised, fast, explainable via feature attribution |
| Template mining | **Drain3** | Incremental, streaming, bounded-memory log template mining |
| LLM | **Ollama (local)** | Hard privacy constraint — no cloud APIs; `format=json` for structured output |
| Experiment tracking | **MLflow** | Datasets, params, metrics, artifacts, model registry |
| Event bus / cache / RL | **Redis 7** | Pub/sub for live updates, queues for the worker, rate-limit buckets |
| Auth | **JWT + Argon2id + RBAC** | Stateless auth, memory-hard hashing, role-based access |
| Logging | **structlog** | Structured, queryable logs surfaced in the product |
| Metrics | **prometheus-client** | Latency/throughput/resource metrics for Live Monitoring |
| Frontend | **Next.js 15 / React 19 / TS** | App Router, RSC, mature enterprise-grade DX |
| Styling / UI | **Tailwind v4 + shadcn/ui** | Accessible Radix primitives; premium dark theme |
| Server state | **TanStack Query v5** | Caching, background refetch, optimistic updates |
| Charts | **Recharts** | Composable, themeable SOC dashboards |
| Motion | **Framer Motion** | Purposeful, accessible micro-interactions |
| Containers | **Docker + Compose** | One-command local bring-up of the full stack |
| CI | **GitHub Actions** | Lint (ruff), format, type (mypy/tsc), tests, build |
| Hooks | **pre-commit** | ruff, mypy, prettier, eslint before every commit |

## 9. Cross-cutting concerns

- **Configuration** — `pydantic-settings`, 12-factor, env-driven. No secret is
  ever hard-coded; `.env.example` documents every variable; secrets are injected.
- **Security** — see [`adr/0006-security-model.md`](./adr/0006-security-model.md):
  Argon2id password hashing, short-lived access JWTs + refresh rotation, RBAC
  (roles: `admin`, `analyst`, `viewer`), per-identity rate limiting, security
  headers (CSP, HSTS, X-Frame-Options), audit log of every privileged action.
- **Observability** — request-scoped correlation IDs, structured logs, Prometheus
  metrics (`api_latency`, `inference_latency`, `logs_per_sec`, `alerts_per_10k`,
  CPU/RAM gauges), all exposed to the Live Monitoring page over WebSocket.
- **Error handling** — typed domain errors mapped to RFC-9457 `problem+json`
  responses; the LLM path has explicit timeout, retry, and fallback behavior; the
  verifier is a hard gate, not a warning.

## 10. Deployment model

`docker compose up` brings the full stack online locally. Production targets a
container platform (backend/worker on Railway/Render/VPS, frontend on Vercel,
managed Postgres + Redis). Images are multi-stage and slim; the training deps
(`ml/`) are never shipped in the serving image.
