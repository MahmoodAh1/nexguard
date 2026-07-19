# ADR 0003 — Local LLM triage with a hard verification gate

- **Status:** Accepted
- **Date:** 2026-07-19

## Context
The triage copilot must draft analyst-ready incident reports **locally** (privacy
constraint: no cloud APIs), and it must never fabricate evidence — a hallucinated
host, timestamp, or log line in a security report is worse than no report.

## Decision
- **Ollama** is the only LLM backend, behind an `LLMProvider` port. A
  deterministic **stub adapter** implements the same port for CI/tests, so the
  pipeline is verifiable without a running model.
- Reports are **Pydantic-schema-constrained** (Ollama `format=json` + schema in
  the prompt). Output feeding app logic is never regex-parsed free text.
- MITRE ATT&CK techniques are **always marked "Hypothesis"**, never asserted as
  confirmed fact — enforced by the schema (a `mitre_hypotheses` field, no
  "confirmed technique" field exists).
- A **`ReportVerifier`** is a hard gate: every citation (event, host, timestamp,
  component) must resolve against the `EvidenceIndex` built from persisted data.
  Any unresolved reference → the report is **rejected** with a reason, not shown.

## Consequences
- Structured, auditable reports; zero cloud data egress.
- The verifier turns "trust the LLM" into "verify the LLM" — the design's core
  safety property.
- Rejected reports are surfaced (with reason) so the failure is observable, not
  silent.
