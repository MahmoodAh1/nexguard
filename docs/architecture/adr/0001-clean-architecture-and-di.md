# ADR 0001 — Clean Architecture with an explicit composition root

- **Status:** Accepted
- **Date:** 2026-07-19

## Context
NexGuard integrates many volatile external concerns (PyTorch, Ollama, SQLAlchemy,
Redis, MLflow). If use cases depend on these directly, the system becomes
untestable and rigid, and a demo-grade coupling sets in.

## Decision
Adopt Clean Architecture / Ports & Adapters. `domain` defines entities, value
objects, and **ports** (Protocols). `application` orchestrates ports in use
cases. `infrastructure` provides adapters. `interfaces` holds delivery
mechanisms (FastAPI/WS/CLI) and the **composition root** — a single, explicit
container that wires concrete adapters to ports and injects them via FastAPI
`Depends`. No service locator, no import-time global singletons.

We hand-roll the container (typed provider functions) rather than adopt a DI
framework: the wiring stays transparent and greppable, which reviewers value more
than framework magic for a codebase this size.

## Consequences
- Use cases are unit-testable with in-memory fakes; adapters are integration-tested.
- Swapping LSTM↔Transformer, SQLite↔Postgres, Ollama↔stub touches one adapter.
- Slightly more boilerplate (interfaces + wiring) — accepted as the cost of
  testability and long-term extensibility.
