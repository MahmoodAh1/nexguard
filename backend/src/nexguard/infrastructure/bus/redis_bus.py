"""Redis-backed event bus.

The production :class:`~nexguard.domain.ports.EventBus` adapter (ADR-0004). Uses
Redis pub/sub: domain events are published as JSON on a channel named for their
topic; subscribers receive decoded payloads. The API bridges these to browser
WebSocket clients. Interchangeable with the in-memory adapter behind the port.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from redis.asyncio import Redis

from nexguard.domain.events import DomainEvent

_WILDCARD = "*"


class RedisEventBus:
    """Redis pub/sub implementation of the EventBus port."""

    def __init__(self, url: str, *, redis: Redis | None = None) -> None:
        # Fail fast: an unreachable broker must surface an error, never hang the
        # request (or the seed pipeline) indefinitely. redis.asyncio defaults to
        # no connect/read timeout, so we set them explicitly.
        self._redis: Redis = redis or Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=5.0,
            socket_timeout=5.0,
            socket_keepalive=True,
        )

    async def publish(self, event: object) -> None:
        if not isinstance(event, DomainEvent):
            raise TypeError(f"RedisEventBus can only publish DomainEvent, got {type(event)!r}")
        await self._redis.publish(event.topic, json.dumps(event.to_payload()))

    async def subscribe(self, topic: str) -> AsyncIterator[dict[str, object]]:
        pubsub = self._redis.pubsub()
        if topic == _WILDCARD:
            await pubsub.psubscribe(_WILDCARD)
        else:
            await pubsub.subscribe(topic)
        try:
            async for message in pubsub.listen():
                if message["type"] in ("message", "pmessage"):
                    yield json.loads(message["data"])
        finally:
            if topic == _WILDCARD:
                await pubsub.punsubscribe(_WILDCARD)
            else:
                await pubsub.unsubscribe(topic)
            await pubsub.aclose()

    async def ping(self) -> bool:
        return bool(await self._redis.ping())

    async def close(self) -> None:
        await self._redis.aclose()
