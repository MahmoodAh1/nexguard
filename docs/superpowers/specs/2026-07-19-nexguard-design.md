# NexGuard — Design Spec

- **Date:** 2026-07-19
- **Status:** For approval (Gate 0)
- **Build strategy:** vertical-slice-first, phase-gated (see
  [`../../architecture/build-plan.md`](../../architecture/build-plan.md))

This spec is the single-entry index to the design. The detailed architecture is
authoritative in [`docs/architecture/`](../../architecture/README.md); this file
states the problem, scope, decisions, and acceptance criteria so the design can
be reviewed as a unit.

## Problem
SOC analysts face crushing alert fatigue and false positives. NexGuard reduces
both with a layered, explainable anomaly-detection stack, a **local** LLM triage
copilot that drafts verified incident reports, and an analyst feedback loop that
measurably improves precision/recall. Fully local, privacy-preserving.

## Goals
- Detect sequence and statistical anomalies in security logs (HDFS primary; BGL,
  CICIDS supported).
- Every alert is explainable (predicted vs actual event, confidence, suspicious
  subsequence, top features).
- Generate analyst-ready incident reports with a local LLM, **verified** against
  real evidence (no fabrication; MITRE as hypothesis only).
- Feedback loop with before/after precision/recall via recalibration.
- Enterprise web console (8 pages), real-time via WebSocket.
- Production-grade: auth/RBAC/audit, tests, observability, MLOps, DevOps.

## Non-goals (initial)
- Cloud LLM APIs (explicitly excluded — local only).
- Horizontal auto-scaling / Kafka-scale infra (interfaces preserve the path; not
  built now).
- Streamlit or any non-professional UI.

## Key decisions (ADRs)
- [0001](../../architecture/adr/0001-clean-architecture-and-di.md) Clean
  Architecture + explicit composition root.
- [0002](../../architecture/adr/0002-detection-approach.md) DeepLog + Isolation
  Forest + Ensemble.
- [0003](../../architecture/adr/0003-local-llm-triage-and-verification.md) Local
  Ollama + hard verification gate.
- [0004](../../architecture/adr/0004-realtime-transport.md) Redis event bus behind
  a port; WebSocket to browser.
- [0005](../../architecture/adr/0005-datasets-and-reproducibility.md) HDFS
  primary; bundled fixture + reproducible download.
- [0006](../../architecture/adr/0006-security-model.md) JWT + Argon2id + RBAC +
  audit.

## Architecture summary
Clean Architecture Python monorepo: `backend/` (the `nexguard` package + FastAPI
app), `ml/` (offline training/eval + MLflow), `services/` (stream workers),
`frontend/` (Next.js). Ports/adapters isolate PyTorch, sklearn, Drain3, Ollama,
SQLAlchemy, Redis, MLflow. See
[architecture/README.md](../../architecture/README.md).

## Acceptance criteria — Checkpoint 1 (the vertical slice)
See [build-plan.md §Phase 1](../../architecture/build-plan.md). In short: a real
end-to-end path — ingest HDFS fixture → Drain3 parse → LSTM + IsolationForest →
ensemble → explained alert → Ollama report + verifier → FastAPI REST/WS with
auth/RBAC/audit → one live Next.js page — with tests at every layer (incl. a
seeded anomaly regression test) and `docker compose up` bringing it online.

## Risks & mitigations
- **Ollama absent in an environment** → stub `LLMProvider` adapter keeps the
  pipeline runnable and tested; real reports need a local model.
- **Model training time/variance** → tiny fixture + fixed seeds for CI; MLflow
  for full runs; seeded regression tests pin behavior.
- **Scope** → phase gates prevent a 300-file placeholder dump; each phase closes
  with runnable, tested code.
