# Data Model

Domain entities and their persistence schema. Dev uses SQLite, production uses
PostgreSQL; the SQLAlchemy 2.0 typed models are identical, with dialect-specific
types (e.g. `JSONB` on Postgres, `JSON` on SQLite) resolved via SQLAlchemy's
generic `JSON`. Schema evolution is managed by Alembic.

## Entities

```
User ──1:N── AuditLog
                                      ┌── DetectionRun ──1:N── Alert
Template ──N:M(vocab)── Session ──────┤
   │                        │         └── SessionFeature (count-vector, derived)
   │                        │
LogEvent ──N:1── Session    │
                            │
Alert ──1:1?── IncidentReport ──1:N── ReportCitation (verified refs)
  │
  └──1:N── Feedback (analyst labels)

CalibrationSnapshot   (thresholds/weights before & after feedback)
```

### Core tables

| Table | Key columns | Notes |
|-------|-------------|-------|
| `users` | id, email(unique), password_hash(argon2), role, is_active, created_at | RBAC role ∈ {admin, analyst, viewer} |
| `audit_logs` | id, actor_id, action, resource, ip, at, metadata(json) | append-only; every privileged action |
| `templates` | id, event_id(unique), template_str, first_seen, last_seen, occurrences | Drain3 vocabulary, stable EventId |
| `sessions` | id, external_id(block_id), dataset, event_count, started_at, ended_at, label(nullable) | label only for eval datasets |
| `log_events` | id, session_id(fk), template_id(fk), raw, params(json), ts, line_no | ordered by (session_id, line_no) |
| `session_features` | session_id(fk), count_vector(json), length, unique_templates, rare_ratio | statistical-model input cache |
| `detection_runs` | id, session_id(fk), model_versions(json), created_at, latency_ms | one scoring pass |
| `alerts` | id, session_id(fk), run_id(fk), score, severity, status, evidence(json), created_at | evidence = full Explainability object |
| `incident_reports` | id, alert_id(fk unique), payload(json), verified(bool), rejected_reason, model, created_at | Pydantic report; payload validated |
| `report_citations` | id, report_id(fk), kind, ref, verified(bool) | verifier output; kind ∈ {event,host,timestamp,component} |
| `feedback` | id, alert_id(fk), analyst_id(fk), label, note, created_at | label ∈ {TP, FP, benign, unknown} |
| `calibration_snapshots` | id, kind(before/after), precision, recall, params(json), created_at | feedback recalibration metrics |

### Value objects (not tables — embedded)

- `Score` — float in `[0,1]` with the component breakdown.
- `Severity` — enum `low/medium/high/critical`, derived from score bands.
- `Evidence` — the structured explainability object (see detection-pipeline.md §6),
  stored as JSON on `alerts`.
- `IncidentReportPayload` — the Pydantic schema (summary, severity, confidence,
  timeline, affected_components, evidence, mitre_hypotheses, investigation_steps,
  containment_actions), stored as JSON on `incident_reports`.

## Alert lifecycle (status)

```
NEW ──▶ TRIAGED ──▶ INVESTIGATING ──▶ RESOLVED
  └──────────────▶ DISMISSED (with feedback: FP / benign)
```

Status transitions are audited. Feedback attaches at any status and feeds
recalibration.

## Migrations

Alembic autogenerate is used, but every migration is hand-reviewed (autogenerate
misses some constraints). The initial migration creates the full schema above;
each subsequent schema change ships its own revision. Downgrade paths are
provided for reversibility.
