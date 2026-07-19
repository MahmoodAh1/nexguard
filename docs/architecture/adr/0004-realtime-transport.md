# ADR 0004 — Redis-backed event bus for real-time, behind a port

- **Status:** Accepted
- **Date:** 2026-07-19

## Context
The dashboard must update live (new alerts, reports, metrics, processing status),
and the ingestion→detection→alerting flow needs a decoupled pipeline between the
worker and the API. We need real-time without over-engineering to Kafka for a
locally-runnable product.

## Decision
Define an `EventBus` port (`publish` / `subscribe`). Default adapter is **Redis
pub/sub + streams** (also used for work queues, rate-limit buckets, and hot
cache). An **in-memory adapter** implements the same port for tests. The API
bridges bus topics to browser **WebSockets**.

Kafka is intentionally *not* adopted now — the port preserves the upgrade path,
and Redis meets throughput needs for the target scale without the operational
cost.

## Consequences
- One dependency (Redis) covers bus + queue + cache + rate limiting.
- Live updates are decoupled from request handling.
- Tests run against the in-memory bus — no Redis required in CI unit tests.
