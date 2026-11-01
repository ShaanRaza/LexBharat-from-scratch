"""Answer cache (Redis). The ONLY file that talks to Redis for caching.

Key = exact match on (rewritten query + filters + model name). 7 days. Only verified
answers are stored and upload chats are never cached - the pipeline enforces both; this
adapter just stores and returns opaque strings.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Protocol

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
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ttl_days: int) -> None:
        self.data[key] = value
        self.ttls[key] = ttl_days
