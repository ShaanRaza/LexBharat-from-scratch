"""Step 4 - CACHE: exact match on (rewritten query + filters + model name).

A hit skips steps 5-8 and costs nothing against the user's limit. Only answers that
passed verification are stored (see core.save). Upload chats never use the cache.
Note: even on a hit the verifier still runs (see core.pipeline) - a deliberate choice.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

from adapters.cache import AnswerCache
from adapters.qdrant import SearchFilters
from core.models import CacheLookup


def cache_key(query: str, filters: SearchFilters, model: str) -> str:
    raw = json.dumps(
        {"q": query.strip().casefold(), "f": dataclasses.asdict(filters), "m": model},
        sort_keys=True,
    )
    return "answer:" + hashlib.sha256(raw.encode()).hexdigest()


async def cache_lookup(
    query: str,
    filters: SearchFilters,
    model: str,
    cache: AnswerCache,
    *,
    is_upload_chat: bool = False,
) -> CacheLookup:
    key = cache_key(query, filters, model)
    if is_upload_chat:  # uploads are private: never read from or written to the cache
        return CacheLookup(key=key, hit=False)
    payload = await cache.get(key)
    return CacheLookup(key=key, hit=payload is not None, payload=payload)
