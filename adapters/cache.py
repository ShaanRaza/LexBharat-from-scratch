"""Answer cache adapter (Redis).

Rule 1 spirit: the rest of the code never imports `redis`; it uses `AnswerCache`.
Pipeline step 4 (Cache). Key = hash of (rewritten query + filters + model name); TTL is
ANSWER_CACHE_TTL_DAYS (7). Only answers that passed verification are stored, and upload
chats are never cached (docs/ARCHITECTURE.md "Caching").

Only the interface and an in-memory Fake live here; no real Redis.
"""

from __future__ import annotations

from typing import Any, Protocol


class AnswerCache(Protocol):
    async def get(self, key: str) -> dict[str, Any] | None: ...
    async def set(self, key: str, value: dict[str, Any], ttl_days: int) -> None: ...


class FakeCache:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, Any]] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> dict[str, Any] | None:
        return self.data.get(key)

    async def set(self, key: str, value: dict[str, Any], ttl_days: int) -> None:
        self.data[key] = value
        self.ttls[key] = ttl_days
