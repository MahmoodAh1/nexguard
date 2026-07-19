# Build Plan & Checkpoint Gates

NexGuard is built **vertical-slice-first**: one complete, real path through every
layer, then iterative deepening. Progress is gated — work proceeds autonomously
*within* a phase, and pauses at each **gate** for review.

---

## Phase 0 — Architecture (this phase)
**Deliverable:** the documents in `docs/architecture/` + ADRs + design spec.
**Gate 0:** architecture & structure approved. ⤶ _you are here_

## Phase 1 — Vertical slice (Checkpoint 1)
One thin-but-**real** path end to end. Definition of done:

1. **Scaffold** the monorepo (backend package, frontend app, docker, CI, tooling).
2. **Ingest** an HDFS fixture (bundled sample) via the `IngestLogs` use case.
3. **Parse** with Drain3 → templates + stable `EventId`s → sessions by `block_id`,
   persisted (SQLite).
4. **Detect** — LSTM sequence model + IsolationForest, each behind its port,
   trained on the fixture's normal sessions; **ensemble** produces score+severity.
5. **Explain** — assemble the `Evidence` object (predicted vs actual, confidence,
   suspicious subsequence, top features).
6. **Alert** — persist, publish `alert.created` on the Redis event bus.
7. **Triage** — `GenerateReport` via the Ollama adapter (deterministic stub in CI)
   → Pydantic-validated `IncidentReport`; **verifier** checks every citation
   against the evidence index and rejects fabrications.
8. **API** — FastAPI: auth (login→JWT), `/alerts`, `/alerts/{id}/report`, and a
   WebSocket channel streaming new alerts. RBAC + rate limit + audit on the path.
9. **UI** — Next.js: login + one live Executive-Dashboard/Alert view that streams
   alerts over WS and opens a report drawer.
10. **Tests** at every layer (domain unit, adapter integration, API, one e2e) +
    seeded anomaly regression test. `docker compose up` runs the whole thing.

**Gate 1:** the slice runs, tests pass, demoable.

## Phase 2 — Deepen detection & MLOps
Transformer variant; full evaluation harness (Precision/Recall/F1/ROC-AUC/PR-AUC/
confusion/FPR/FNR + operational metrics); MLflow tracking; threshold calibration;
BGL + CICIDS adapters proving the abstractions generalize; benchmarks.
**Gate 2.**

## Phase 3 — Full platform surface
The remaining pages (Alert Explorer, Incident Reports, Log Explorer, Detection
Analytics, Live Monitoring, Feedback Center, Configuration); full WebSocket
metric streaming; feedback loop + recalibration with before/after precision/recall;
notifications, empty/loading states, accessibility pass.
**Gate 3.**

## Phase 4 — Hardening & delivery
Security hardening pass, observability dashboards, full test matrix (unit /
integration / regression / API / db / ml / frontend / e2e), Docker/Compose
production profile, GitHub Actions CI, pre-commit, README with screenshots +
benchmarks + limitations + roadmap.
**Gate 4 — release candidate.**

---

### Cross-phase invariants (never violated)
- No `TODO` placeholders for core functionality.
- Every module ships with tests, and tests are **run** before a phase closes.
- Every external dependency sits behind a port with a test double.
- Secrets are env-injected; nothing sensitive is committed.
- Docs updated in the same change as the code they describe.
