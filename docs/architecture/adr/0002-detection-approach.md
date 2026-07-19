# ADR 0002 — Layered detection: DeepLog + Isolation Forest + Ensemble

- **Status:** Accepted
- **Date:** 2026-07-19

## Context
No single detector is sufficient. Sequence models catch ordering anomalies but
miss compositional ones; statistical models catch compositional anomalies but are
blind to order. Analysts need **explainable** alerts, not just scores.

## Decision
Ship three cooperating detectors behind ports:
1. **DeepLog-style sequence model** (PyTorch LSTM, with an interchangeable
   Transformer-encoder variant) trained on *normal* sessions via next-event
   prediction. Anomaly = actual next event outside the top-`k` prediction, with
   perplexity and surprising-step fraction as the signal.
2. **Isolation Forest** over session count-vectors, with per-feature attribution.
3. **Ensemble** — calibrated, weighted vote with a configurable threshold.

Training is semi-supervised (normal-only for the sequence model); labels are used
only for evaluation and calibration, matching real unlabeled production telemetry.

## Alternatives considered
- **Supervised classifier** — rejected: needs labeled anomalies at train time,
  which real SOCs lack, and overfits known attacks.
- **Single autoencoder** — rejected: weaker explainability; DeepLog's next-event
  framing yields the predicted-vs-actual evidence analysts need.

## Consequences
- Two complementary detection modalities + an ensemble to reconcile them.
- Explainability is a first-class output, feeding the LLM triage and the verifier.
- More models to train/evaluate/track — handled by the `ml/` harness + MLflow.
