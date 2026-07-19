# ADR 0005 — Datasets: HDFS primary, bundled fixture + reproducible download

- **Status:** Accepted
- **Date:** 2026-07-19

## Context
The full HDFS LogHub dataset is large (~1.5 GB, 11M+ lines) — unsuitable to
commit, but the pipeline, tests, and demo must run reproducibly without a manual
download step. We also must support BGL and CICIDS-style data.

## Decision
- **Primary: HDFS** — session-partitioned by `block_id` with block-level labels,
  the ideal shape for sequence + statistical detection (justified in the
  architecture overview).
- Commit a **small, labeled HDFS fixture** (a few hundred blocks, both classes)
  under `backend/tests/fixtures` / `ml/data/samples` for deterministic tests and
  demo.
- Provide `scripts/download_data.py` to fetch the **full** LogHub datasets
  (HDFS/BGL) on demand, with checksum verification, for real training.
- Model all datasets behind a `DatasetAdapter` port (`iter_sessions()`), so
  BGL/CICIDS plug in without touching detection code.

## Consequences
- Reproducible: `pytest` and a demo run offline against the fixture; full
  training is one script away.
- Dataset generality is proven by having ≥2 adapters against one interface.
- No large binaries in git history.
