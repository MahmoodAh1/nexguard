# NexGuard — Offline ML / MLOps

The **offline** side of NexGuard: training, model comparison, evaluation, and
experiment tracking. It is intentionally separate from the serving path
(`backend/`) — heavier, batch-oriented, and never shipped in the API image.

The reusable evaluation library lives in the package
(`nexguard.evaluation`, fully typed + tested); the scripts here orchestrate it.

## Run the model comparison

```bash
cd backend && uv run python ../ml/evaluate.py            # HDFS fixture
cd backend && uv run python ../ml/evaluate.py --epochs 30 --threshold 0.5
```

Trains LSTM, Transformer, Isolation Forest, and the Ensemble on the *normal*
sessions and evaluates all four on the labeled set. Output → `results/model_comparison.md`.

## What the comparison shows (and why it matters)

On the bundled HDFS fixture:

| Model | F1 | ROC-AUC | FPR | Note |
|-------|----|---------|-----|------|
| LSTM | 1.00 | 1.00 | 0.00 | strong — carries detection here |
| Transformer | 1.00 | 1.00 | 0.00 | matches LSTM, ~2× slower |
| Isolation Forest | 0.25 | 0.50 | 1.00 | **weak on this fixture** — see below |
| Ensemble | 1.00 | 1.00 | 0.00 | sequence signal dominates the vote |

**Isolation Forest looks bad here, and that's honest, not a bug.** The fixture's
anomalies are dominated by *new* templates (write exceptions, deletions) that never
appear in normal training, so they fall outside IForest's feature space — it can
only reason about the composition of *known* templates. On this data that leaves it
near-random (ROC-AUC ≈ 0.5), flagging everything (FPR = 1.0). It earns its keep on
*compositional* anomalies (a known template appearing far more/less than usual),
which this fixture doesn't emphasize — exactly why the two detectors are
complementary and why the **ensemble** is the right default.

**Analyst-workload framing:** IForest alone would raise ~10,000 alerts per 10k
sessions (every session) — operationally useless. The ensemble raises ~1,429 per
10k, matching the true anomaly rate, at 100% precision. FPR × session volume is the
daily false-alert load a SOC actually pays for.

## Roadmap (Phase 2)

- MLflow experiment tracking (datasets, params, metrics, ROC/PR artifacts)
- Threshold/weight calibration against a target operating point
- BGL / CICIDS adapters + full LogHub-dataset benchmarks (`scripts/download_data.py`)
