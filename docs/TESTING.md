# Testing

NexGuard covers the full test matrix the spec asks for. Every layer is exercised;
CI runs all of it on each push/PR.

| Layer | What it covers | Location | Run |
|-------|----------------|----------|-----|
| **Unit** | Domain value objects/entities/ports, evidence + report schemas, security (Argon2/JWT/RBAC), settings, ensemble, metrics, calibration, feedback + detect use cases | `backend/tests/unit/` | `uv run pytest tests/unit` |
| **Integration (adapters)** | Real SQLite repositories, Drain3 miner, HDFS/BGL/CICIDS sources, ingest use case, in-memory adapters | `backend/tests/integration/{db,parsing,datasets,application}` | `uv run pytest tests/integration` |
| **ML pipeline** | LSTM + Transformer detectors, Isolation Forest (calibration + attribution), evaluation harness/metrics/calibration, MLflow tracker (skips w/o the extra) | `backend/tests/integration/{detection,evaluation,tracking}` | `uv run pytest -m slow` |
| **Database** | ORM ↔ domain mappers, CRUD/filter/aggregation over real SQLite | `backend/tests/integration/db` | included above |
| **API** | Auth + refresh, RBAC, security headers, rate limiting, alerts, reports, detection, **feedback + recalibration**, sessions/templates, analytics, config, Prometheus `/metrics` | `backend/tests/integration/api` | `uv run pytest tests/integration/api` |
| **WebSocket** | Live `alert.created` and `metrics.tick` streams, auth rejection | `backend/tests/integration/api/test_ws.py` | included above |
| **Regression** | Seeded HDFS anomaly regression — pins 10/10 recall, 0 FP end to end | `backend/tests/regression` | `uv run pytest tests/regression` |
| **Frontend (unit/component)** | `cn`/time utils, alerts table, feedback controls (mocked data layer) | `frontend/src/**/*.test.tsx` | `npm run test` |
| **E2E (browser)** | Playwright: analyst login → live dashboard → Alert Explorer, against a seeded stack | `frontend/e2e/` | `npm run e2e` |

## Determinism

ML tests fix seeds (torch `manual_seed`, sklearn `random_state`) and use a small
committed HDFS fixture, so results are reproducible. `slow`-marked tests train real
models on CPU (a few seconds each).

## Running everything

```bash
# Backend (166 tests) with coverage
cd backend && uv run pytest -q --cov=nexguard

# Frontend unit/component (12 tests)
cd frontend && npm run test

# E2E — start a seeded backend + the frontend first, then:
cd frontend && npm run e2e
```

## CI

`.github/workflows/ci.yml` runs, in parallel jobs: **backend** (ruff · ruff-format
· mypy --strict · pytest+coverage), **frontend** (vitest · production build),
**security** (gitleaks · pip-audit · npm audit), **e2e** (boots seeded API +
frontend, runs Playwright/Chromium), and **docker** (builds both images).
