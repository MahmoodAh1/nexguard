# Build Plan & Checkpoint Gates

NexGuard is built **vertical-slice-first**: one complete, real path through every
layer, then iterative deepening. Progress is gated — work proceeds autonomously
*within* a phase, and pauses at each **gate** for review.

---

## Phase 0 — Architecture ✅ COMPLETE
**Deliverable:** the documents in `docs/architecture/` + ADRs + design spec.
**Gate 0:** architecture & structure approved.

## Phase 1 — Vertical slice (Checkpoint 1) ✅ COMPLETE
One thin-but-**real** path end to end — delivered: 134 tests (123 backend + 11
frontend), `mypy --strict` clean, seeded regression at 10/10 recall & 0 false
positives, `docker compose up` brings the full stack online. Definition of done:

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

## Phase 2 — Deepen detection & MLOps ✅ COMPLETE
Transformer variant (shared scoring base); full evaluation harness (Precision/
Recall/F1/ROC-AUC/PR-AUC/confusion/FPR/FNR + operational: latency p50/p95,
throughput, alerts/10k); model comparison (LSTM/Transformer/IForest/Ensemble);
MLflow tracking behind an ExperimentTracker port (isolated offline env);
ensemble weight+threshold calibration with before/after metrics; BGL + CICIDS
adapters proving the DatasetSource abstraction generalizes; committed benchmarks
([docs/benchmarks.md](../benchmarks.md)) + reproducible full-dataset download.
**Gate 2 reached.**

## Phase 3 — Full platform surface ✅ COMPLETE
All 8 console pages live (Executive Dashboard + Alert Explorer, Incident Reports,
Log Explorer, Detection Analytics, Live Monitoring, Feedback Center, Configuration);
WebSocket metric streaming (`/ws/metrics`); analyst feedback loop + recalibration
with persisted before/after precision/recall (`CalibrationSnapshot`); runtime-
adjustable operating point (admin) with audit; sessions/templates/analytics/config
APIs; loading + empty states throughout. **Gate 3 reached.**

## Phase 4 — Hardening & delivery ✅ COMPLETE
Security hardening pass (refresh-token rotation, CSP/HSTS/X-Frame security headers
front+back, `SECURITY.md` threat model, CI supply-chain audits: gitleaks / pip-audit
/ npm audit); observability (Prometheus metrics via middleware + Grafana dashboards,
compose profile); full test matrix (unit / integration / regression / API / db / ml /
frontend / **Playwright e2e**) documented in [docs/TESTING.md](../TESTING.md) and run
in CI; Docker/Compose production profile; GitHub Actions CI (lint · type · test ·
coverage · security · e2e · image builds); pre-commit; one-command deploy
([render.yaml](../../render.yaml) blueprint + Vercel, guide in
[docs/DEPLOYMENT.md](../DEPLOYMENT.md)); [CHANGELOG.md](../../CHANGELOG.md) v0.1.0;
README refreshed (benchmarks + limitations + roadmap + deploy).
**Gate 4 reached — v0.1.0 release candidate.**

---

### Cross-phase invariants (never violated)
- No `TODO` placeholders for core functionality.
- Every module ships with tests, and tests are **run** before a phase closes.
- Every external dependency sits behind a port with a test double.
- Secrets are env-injected; nothing sensitive is committed.
- Docs updated in the same change as the code they describe.
