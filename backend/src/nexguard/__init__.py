"""NexGuard — AI-Powered Security Operations Platform (backend).

The package is organized in Clean Architecture layers, with dependencies pointing
inward only:

- ``domain``         — entities, value objects, and ports (Protocols). No framework deps.
- ``application``    — use cases orchestrating the ports.
- ``infrastructure`` — adapters implementing the ports (db, parsing, detection, llm, bus).
- ``interfaces``     — delivery mechanisms (FastAPI, WebSocket, CLI) + composition root.
- ``config`` / ``observability`` / ``security`` — cross-cutting concerns, injected.

See ``docs/architecture/README.md`` for the full design.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
