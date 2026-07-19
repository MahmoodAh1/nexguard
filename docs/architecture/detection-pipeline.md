# Detection Pipeline — Design

This is the flagship of NexGuard: a layered anomaly-detection stack that is
**explainable by construction** and **evaluable end-to-end**. It combines a
DeepLog-style deep-sequence model, a statistical model, and an ensemble, then
attaches human-readable evidence to every alert.

---

## 1. Problem framing

Given a stream of raw log lines partitioned into **sessions** (for HDFS, one
session per `block_id`), decide for each session whether its behavior is
anomalous, produce a **calibrated score** and **severity**, and produce
**evidence** an analyst can act on. Training is **semi-supervised**: models learn
the distribution of *normal* sessions; anomalies are deviations. Ground-truth
labels (HDFS ships block-level normal/anomaly labels) are used only for
**evaluation and threshold calibration**, never as a training signal for the
sequence model — this mirrors how the system must work on unlabeled production
telemetry.

## 2. From raw logs to model inputs

```
raw line ──Drain3──▶ template (stable EventId) ──┐
                                                 ├─▶ per session:
raw line ──Drain3──▶ template (stable EventId) ──┤     • event-id SEQUENCE  → sequence model
                                                 │     • event-id COUNT VEC  → statistical model
raw line ──Drain3──▶ template (stable EventId) ──┘
```

- **Drain3** performs incremental, streaming template mining with bounded memory
  (fixed-depth parse tree). Each unique template is assigned a stable integer
  `EventId`; the mapping is persisted so the same template always maps to the
  same id across restarts and across train/serve.
- A **Session** is the ordered list of `EventId`s for a `block_id`, plus a
  count-vector (histogram over the template vocabulary). The sequence model
  consumes the ordered sequence; the statistical model consumes the count-vector.

## 3. Model A — DeepLog-style sequence detector (PyTorch)

**Task:** next-event prediction. Trained only on *normal* sessions to learn the
grammar of legitimate execution. At inference, a session is anomalous if the
model is repeatedly *surprised* by the actual next event.

- **Input:** sliding windows of length `w` over the event-id sequence.
- **Architecture (two interchangeable variants behind one port):**
  - **LSTM** — embedding → stacked LSTM → linear head over the template vocab.
  - **Transformer encoder** — embedding + positional encoding → N encoder blocks
    → linear head. Captures long-range dependencies; compared head-to-head in
    evaluation.
- **Anomaly rule:** for each step, the model predicts a probability distribution
  over the next `EventId`. If the *actual* next event is **not in the top-`k`**
  most-probable predictions, that step is flagged. A session's anomaly signal is
  derived from:
  - the **fraction of surprising steps**,
  - the **sequence perplexity** (exp of mean negative log-likelihood), and
  - the **minimum top-k rank margin**.
- **Per-alert evidence emitted:** anomaly score, the predicted top-k events, the
  actual event, model confidence, and the exact **suspicious subsequence** (the
  window(s) where prediction failed). This directly satisfies the requirement
  that every alert carry predicted vs. actual, confidence, and the offending
  subsequence.

## 4. Model B — Statistical detector (Isolation Forest)

**Task:** unsupervised outlier detection over **session-level count-vectors**.

- **Features:** normalized event-id count vector per session (+ derived features:
  session length, unique-template count, rare-template ratio).
- **Model:** scikit-learn `IsolationForest`. Score = normalized anomaly score
  (higher = more anomalous), robust and cheap.
- **Explanation:** per-session **feature attribution** — which template counts
  most drove the score (via per-feature isolation depth deltas / a permutation
  fallback). Emitted as "important features" on the alert.

Isolation Forest complements the sequence model: it catches sessions whose
*composition* is abnormal even when local ordering looks fine (and vice-versa).

## 5. Ensemble layer

Combines the two verdicts into one decision.

- **Normalization:** both raw scores are mapped to `[0,1]` via fitted calibrators
  (min-max / quantile on a validation split) so they are comparable.
- **Combination:** configurable **weighted vote**
  `score = w_seq · s_seq + w_stat · s_stat` (weights in config), plus a
  `max`/`or` policy option for high-recall regimes.
- **Thresholding:** a configurable decision threshold maps `score → {alert,
  no-alert}`; severity buckets (`low/medium/high/critical`) are threshold bands.
- **Calibration:** thresholds and weights are *fitted* against a labeled
  validation split to hit an operating point (e.g. target FPR), and are
  **recalibrated** by the feedback loop. All parameters are versioned artifacts,
  tracked in MLflow.

## 6. Explainability contract

Every `Alert` carries a structured `Evidence` object, assembled from both models:

```
Evidence
├── sequence:  predicted_topk, actual_event, confidence, suspicious_subsequence,
│              perplexity, surprising_step_indices
├── statistical: anomaly_score, important_features[(template, contribution)]
├── ensemble:  weights, component_scores, final_score, threshold, severity
└── provenance: session_id, block_id, event_count, time_range
```

This is what the LLM triage copilot consumes, and what the verifier checks
against — the evidence is the single source of truth, so the report *cannot*
reference anything not present here without failing verification.

## 7. Evaluation harness (`ml/`)

Model comparison across **LSTM, Transformer, Isolation Forest, Ensemble** on a
held-out labeled split. Metrics:

- **Quality:** Precision, Recall, F1, ROC-AUC, PR-AUC, confusion matrix, FPR, FNR.
- **Operational:** detection latency, inference latency (p50/p95), CPU%, memory,
  logs/sec throughput, **alerts per 10k logs**.
- **Analyst-workload framing:** every metric is tied back to its effect on the
  analyst — e.g. FPR × volume = false alerts/shift; recall = missed incidents.
  The evaluation report explicitly discusses the precision/recall trade-off in
  terms of *analyst hours*, not just abstract numbers.

All runs are logged to **MLflow**: dataset hash, hyperparameters, metrics,
artifacts (ROC/PR curves, confusion matrices, calibrators, model weights). Runs
are reproducible from a config + a seed.

## 8. Regression testing

- **Seeded anomaly regression tests:** a fixed fixture of known-anomalous and
  known-normal sessions with pinned expected verdicts. CI fails if a model change
  silently regresses detection on these seeded cases.
- **Determinism:** seeds fixed; the stub/CPU path produces stable scores so the
  pipeline is testable without a GPU.

## 9. Serving vs. training boundary

- **Training/eval** lives in `ml/` (offline, heavier deps, MLflow). It produces
  **versioned model artifacts** (weights, calibrators, template vocab).
- **Serving** lives in `backend/infrastructure/detection` (the adapters behind
  `SequenceDetector` / `StatisticalDetector` / `Ensemble` ports). It **loads**
  artifacts and scores in the request/stream path. The two never share process
  or dependency footprint — training deps never enter the API image.
