"""Voyage AI: query embeddings and re-ranking. The ONLY file that talks to Voyage.

Plain words: the rest of the code calls embed(text) and rerank(query, docs). If Voyage
is swapped, only this file changes. A query embedding must use the model that built the
vectors of the collection being searched; the model name comes from
settings.embed_model_for(collection), which refuses a collection nobody has measured.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

import httpx

from adapters.guard import refuse_in_production
from core.settings import Settings

_BASE = "https://api.voyageai.com/v1"
DIM = 1024


class VoyageUnavailable(Exception):
    """Voyage is down or timed out. Search falls back to keyword only."""


class Embedder(Protocol):
    async def embed(self, text: str, collection: str) -> list[float]: ...


class Reranker(Protocol):
    async def rerank(
        self, query: str, docs: Sequence[str], top_k: int
    ) -> list[tuple[int, float]]:
        """Return (index into docs, score), best first, at most top_k."""
        ...


class VoyageClient:
    """Real client over HTTPS. Not verified against the live service (no key)."""

    def __init__(self, settings: Settings, timeout_s: float = 5.0):
        self._s = settings
        self._timeout = timeout_s

    async def _post(self, path: str, body: dict) -> dict:
        key = self._s.VOYAGE_API_KEY.get_secret_value()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{_BASE}/{path}",
                    json=body,
                    headers={"Authorization": f"Bearer {key}"},
                )
                r.raise_for_status()
                return r.json()
        except httpx.HTTPError as e:
            raise VoyageUnavailable(str(e)) from e

    async def embed(self, text: str, collection: str) -> list[float]:
        model = self._s.embed_model_for(collection)  # raises before any request is sent
        data = await self._post(
            "embeddings",
            {
                "input": [text],
                "model": model,
                "input_type": "query",
            },
        )
        return data["data"][0]["embedding"]

    async def rerank(
        self, query: str, docs: Sequence[str], top_k: int
    ) -> list[tuple[int, float]]:
        data = await self._post(
            "rerank",
            {
                "query": query,
                "documents": list(docs),
                "model": self._s.VOYAGE_RERANK_MODEL,
                "top_k": top_k,
            },
        )
        return [(r["index"], r["relevance_score"]) for r in data["data"]]


_WORD = re.compile(r"[a-z0-9]+")


def words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


class FakeEmbedder:
    """Deterministic hashed bag-of-words vector. `down=True` simulates an outage."""

    def __init__(self, dim: int = 64, down: bool = False):
        refuse_in_production()
        self.dim, self.down = dim, down
        self.calls = 0

    async def embed(self, text: str, collection: str | None = None) -> list[float]:
        self.calls += 1
        if self.down:
            raise VoyageUnavailable("fake down")
        v = [0.0] * self.dim
        for w in words(text):
            h = int(hashlib.md5(w.encode(), usedforsecurity=False).hexdigest(), 16)
            v[h % self.dim] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]


class FakeReranker:
    """Scores by word overlap with the query. `down=True` simulates an outage."""

    def __init__(self, down: bool = False):
        refuse_in_production()
        self.down = down

    async def rerank(
        self, query: str, docs: Sequence[str], top_k: int
    ) -> list[tuple[int, float]]:
        if self.down:
            raise VoyageUnavailable("fake down")
        q = set(words(query))
        scored = []
        for i, d in enumerate(docs):
            dw = set(words(d))
            scored.append((i, len(q & dw) / (len(q) or 1)))
        scored.sort(key=lambda t: (-t[1], t[0]))
        return scored[:top_k]
