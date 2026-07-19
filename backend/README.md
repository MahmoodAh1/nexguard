# NexGuard — Backend

The `nexguard` Python package: the domain, application use cases, infrastructure
adapters, and the FastAPI/WebSocket delivery layer. Built on Clean Architecture
(see [`../docs/architecture/README.md`](../docs/architecture/README.md)).

## Quickstart

```bash
# from backend/
uv sync --extra dev                     # core + dev tooling
uv sync --extra dev --extra detection   # + PyTorch / scikit-learn (for detection)

uv run pytest                # run the test suite
uv run ruff check .          # lint
uv run mypy                  # type-check (strict)
uv run nexguard --help       # CLI
```

## Layout

```
src/nexguard/
  domain/          entities, value objects, ports (Protocols), errors
  application/     use cases, DTOs
  infrastructure/  adapters: db, parsing, detection, llm, bus, datasets
  interfaces/      FastAPI app, routers, WebSocket, composition root, CLI
  config/          pydantic-settings configuration
  observability/   structured logging, metrics
  security/        hashing, JWT, RBAC
```
