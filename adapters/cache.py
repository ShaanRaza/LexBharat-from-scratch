"""Answer cache (Redis). The ONLY file that talks to Redis for caching.

Key = exact match on (rewritten query + filters + model name). 7 days. Only verified
answers are stored and upload chats are never cached - the pipeline enforces both; this
adapter just stores and returns opaque strings.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Protocol

from adapters.guard import refuse_in_production
from core.settings import Settings

log = logging.getLogger(__name__)


def cache_key(query: str, filters: str, model: str) -> str:
    h = hashlib.sha256(f"{query}\x1f{filters}\x1f{model}".encode()).hexdigest()
    return f"answer:{h}"


class AnswerCache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, ttl_days: int) -> None: ...


class RedisCache:
    """Real. Not verified against a live Redis. A Redis failure is treated as a miss."""

    def __init__(self, settings: Settings):
        import redis.asyncio as redis

        self._r = redis.from_url(settings.REDIS_URL)

    async def get(self, key: str) -> str | None:
        try:
            v = await self._r.get(key)
        except Exception:  # noqa: BLE001
            return None
        return v.decode() if v else None

    async def set(self, key: str, value: str, ttl_days: int) -> None:
        try:
            await self._r.set(key, value, ex=ttl_days * 86400)
        except Exception:  # noqa: BLE001
            log.warning("cache write failed")


class FakeCache:
    def __init__(self) -> None:
        refuse_in_production()
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ttl_days: int) -> None:
        self.data[key] = value
        self.ttls[key] = ttl_days


class RateLimiter(Protocol):
    async def hit(self, key: str, limit: int, window_s: int) -> bool:
        """Count one call under `key`. True = allowed, False = over the limit."""
        ...


class RedisRateLimiter:
    """Fixed window per key (INCR + EXPIRE). FAILS CLOSED: if Redis cannot be reached
    the call is refused, because this guards a paid model call (A52). Not verified
    against a live Redis."""

    def __init__(self, settings: Settings):
        import redis.asyncio as redis

        self._r = redis.from_url(settings.REDIS_URL)

    async def hit(self, key: str, limit: int, window_s: int) -> bool:
        try:
            n = await self._r.incr(key)
            if n == 1:
                await self._r.expire(key, window_s)
            return n <= limit
        except Exception:  # noqa: BLE001
            log.warning("rate limiter unavailable: refusing the call")
            return False


class FakeRateLimiter:
    """In-memory fixed window. `down=True` simulates Redis being unreachable."""

    def __init__(self, down: bool = False) -> None:
        refuse_in_production()
        self.counts: dict[str, int] = {}
        self.down = down

    async def hit(self, key: str, limit: int, window_s: int) -> bool:
        if self.down:
            return False
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key] <= limit
