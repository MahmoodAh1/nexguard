# Changelog

All notable changes to NexGuard are documented here. This project follows
[Semantic Versioning](https://semver.org) and [Keep a Changelog](https://keepachangelog.com).

## [0.1.0] — 2026-07-23

First public release: a complete, local-first AI-powered SOC platform built across
four phases. **181 tests** (169 backend + 12 frontend, plus Playwright e2e),
`mypy --strict` clean.

### Detection & AI
- DeepLog-style **LSTM** and **Transformer** sequence detectors (next-event
  prediction) behind one port, sharing a common scoring base.
- **Isolation Forest** statistical detector with decision-function calibration and
  occlusion-based feature attribution.
- Calibrated **weighted ensemble** with severity banding; explainable-by-construction
  evidence on every alert.
- **Local LLM triage** (Ollama) drafting Pydantic-structured incident reports, with a
  **hard hallucination-verification gate** and MITRE ATT&CK pinned to hypotheses.

### MLOps
- Evaluation harness + metrics (Precision/Recall/F1/ROC-AUC/PR-AUC/confusion/FPR/FNR
  + latency/throughput/alerts-per-10k) and 4-model comparison.
- **MLflow** experiment tracking behind a port (isolated offline environment).
- Ensemble weight + threshold **calibration** with before/after reporting.
- **BGL** and **CICIDS** dataset adapters alongside HDFS.

### Platform
- FastAPI backend: clean architecture, JWT auth + **refresh rotation** + RBAC + audit,
  rate limiting, security headers, RFC-9457 errors, WebSocket live updates.
- **Analyst feedback loop** + recalibration (persisted before/after precision/recall),
  runtime-adjustable operating point.
- Next.js 15 SOC console — **all 8 pages** (Dashboard, Alert Explorer, Incident
  Reports, Log Explorer, Detection Analytics, Live Monitoring, Feedback Center,
  Configuration).

### Ops & security
- **Prometheus** metrics + **Grafana** dashboards; observability compose profile.
- Docker + Compose (prod-style stack), GitHub Actions CI (lint/type/test/coverage,
  security audits, image builds, Playwright e2e), pre-commit hooks.
- `SECURITY.md` threat model, `docs/TESTING.md` matrix, `docs/DEPLOYMENT.md` guide,
  reproducible benchmarks and dataset download.

[0.1.0]: https://github.com/MahmoodAh1/nexguard/releases/tag/v0.1.0
