"""In-memory event bus.

A real adapter (not merely a test double): it backs the ``memory`` event-bus mode
for single-process local runs and CI, and implements the same
:class:`~nexguard.domain.ports.EventBus` port as the Redis adapter. Publishing
fans out to every live subscriber's queue; ``published`` retains history for
assertions and late replay in tests.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from nexguard.domain.events import DomainEvent

_WILDCARD = "*"


class InMemoryEventBus:
    """Asyncio-queue-backed pub/sub for a single process."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, object]]]] = (
            defaultdict(list)
        )
        self.published: list[DomainEvent] = []

    async def publish(self, event: object) -> None:
        if not isinstance(event, DomainEvent):
            raise TypeError(
                f"InMemoryEventBus can only publish DomainEvent, got {type(event)!r}"
            )
        self.published.append(event)
        payload = event.to_payload()
        for topic in (event.topic, _WILDCARD):
            for queue in list(self._subscribers.get(topic, ())):
                await queue.put(payload)

    async def subscribe(self, topic: str) -> AsyncIterator[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        self._subscribers[topic].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._subscribers[topic].remove(queue)

    def subscriber_count(self, topic: str) -> int:
        return len(self._subscribers.get(topic, ()))
