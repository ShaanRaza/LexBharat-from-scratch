"""Voyage AI adapter: turns text into numbers (embed) and re-orders passages (rerank).

Rule 1 (CLAUDE.md): this is the ONLY file that talks to Voyage. The rest of the code
calls `embed(text)` and `rerank(...)` on a `VoyageClient`, never the Voyage library.

Pipeline steps that use it: 5 (search needs the query embedding) and 6 (re-rank).

Only the interface and a Fake live here. A real HTTP client is added later behind the
same interface, reading VOYAGE_API_KEY / VOYAGE_EMBED_MODEL / VOYAGE_RERANK_MODEL from
core/settings.py.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Protocol


class VoyageUnavailable(Exception):
    """Raised when Voyage is down. Search then falls back to keyword-only results."""


@dataclass(frozen=True)
class RerankHit:
    """One re-ranked document: its position in the input list and its score."""

    index: int
    score: float


class VoyageClient(Protocol):
    """What the rest of the code is allowed to ask Voyage for."""

    async def embed(self, text: str) -> list[float]: ...

    async def rerank(
        self, query: str, documents: list[str], top_k: int
    ) -> list[RerankHit]: ...


_WORD = re.compile(r"\w+", re.UNICODE)


def _words(text: str) -> set[str]:
    return {w.casefold() for w in _WORD.findall(text)}


class FakeVoyage:
    """In-memory stand-in for tests. Deterministic, no network.

    - embed: hashes each word into one of 16 buckets (same text -> same vector).
    - rerank: scores by the share of query words found in the document.
    - set `down=True` to simulate Voyage being unavailable.
    """

    DIMS = 16

    def __init__(self, down: bool = False) -> None:
        self.down = down
        self.embed_calls: list[str] = []
        self.rerank_calls: list[tuple[str, int]] = []

    async def embed(self, text: str) -> list[float]:
        if self.down:
            raise VoyageUnavailable("fake voyage is down")
        self.embed_calls.append(text)
        vec = [0.0] * self.DIMS
        for w in _words(text):
            bucket = int(hashlib.md5(w.encode()).hexdigest(), 16) % self.DIMS
            vec[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    async def rerank(
        self, query: str, documents: list[str], top_k: int
    ) -> list[RerankHit]:
        if self.down:
            raise VoyageUnavailable("fake voyage is down")
        self.rerank_calls.append((query, len(documents)))
        q = _words(query)
        hits = [
            RerankHit(i, len(q & _words(d)) / (len(q) or 1))
            for i, d in enumerate(documents)
        ]
        # Highest score first; ties keep the original order (stable sort).
        hits.sort(key=lambda h: -h.score)
        return hits[:top_k]
