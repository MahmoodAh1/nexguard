"""Domain layer: entities, value objects, ports, and domain services.

This layer has **no dependencies on frameworks or infrastructure**. It may use
small, framework-agnostic libraries (``pydantic`` for structured value objects
that must serialize, ``dataclasses`` from the stdlib) but never imports FastAPI,
SQLAlchemy, PyTorch, Redis, or any adapter. Dependencies point inward toward this
layer only.
"""

from __future__ import annotations
