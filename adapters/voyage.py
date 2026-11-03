"""Voyage AI: embeddings and re-ranking. The ONLY file that talks to Voyage (CLAUDE.md
section 2 rule 1; A127).

Plain words: the rest of the code calls embed(...) and rerank(query, docs). If Voyage is
swapped, only this file changes. Two rules live here so nobody can get them wrong:

* The model is the one that built the vectors of the collection being used:
  settings.embed_model_for(collection), which refuses a collection nobody has measured.
* `input_type` is a REQUIRED argument with no default. Voyage embeds a query and a
  document differently, and getting it wrong is silent: a document embedded as a query
  lands at cosine 0.82 to 0.90 against the stored vectors (measured 2 Nov 2026), against
  0.998 or better when "document" is sent. A default would be right for the corpus and
  wrong for every query, so there is none; a caller has to choose.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

from adapters.guard import refuse_in_production
from core.settings import Settings

_BASE = "https://api.voyageai.com/v1"
DIM = 1024

InputType = Literal["query", "document"]
INPUT_TYPES: tuple[str, ...] = ("query", "document")


def check_input_type(input_type: object) -> InputType:
    """Python does not enforce a Literal at runtime, so a typo would reach Voyage."""
    if input_type not in INPUT_TYPES:
        raise ValueError(f"input_type must be 'query' or 'document', got {input_type!r}")
    return input_type  # type: ignore[return-value]


class VoyageUnavailable(Exception):
    """Voyage is down or timed out. Search falls back to keyword only."""


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: list[list[float]]
    total_tokens: int  # as billed by Voyage (0 if the response carries no usage)


class Embedder(Protocol):
    async def embed(
        self,
        text: str,
        collection: str,
        input_type: InputType,
        *,
        court_code: str | None = None,
    ) -> list[float]: ...

    async def embed_batch(
        self,
        texts: Sequence[str],
        collection: str,
        input_type: InputType,
        *,
        court_code: str | None = None,
    ) -> EmbeddingBatch: ...


class Reranker(Protocol):
    async def rerank(
        self, query: str, docs: Sequence[str], top_k: int
    ) -> list[tuple[int, float]]:
        """Return (index into docs, score), best first, at most top_k."""
        ...


class VoyageClient:
    """Real client over HTTPS. The online path (timeout 5 s, one attempt, then keyword
    search takes over) is the default; the corpus scripts ask for a longer timeout and
    retries on a rate limit or a server error."""

    def __init__(
        self,
        settings: Settings,
        timeout_s: float = 5.0,
        max_attempts: int = 1,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._s = settings
        self._timeout = timeout_s
        self._attempts = max(1, max_attempts)
        self._transport = transport

    async def _post(self, path: str, body: dict) -> dict:
        key = self._s.VOYAGE_API_KEY.get_secret_value()
        last: Exception | None = None
        for attempt in range(self._attempts):
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout, transport=self._transport
                ) as c:
                    r = await c.post(
                        f"{_BASE}/{path}",
                        json=body,
                        headers={"Authorization": f"Bearer {key}"},
                    )
                    r.raise_for_status()
                    return r.json()
            except httpx.HTTPStatusError as e:
                last = e
                if e.response.status_code not in (429, 500, 502, 503, 504):
                    break  # a 400 or 401 will not get better by waiting
            except httpx.HTTPError as e:
                last = e
            if attempt + 1 < self._attempts:
                await asyncio.sleep(min(60, 2 ** (attempt + 1)))
        raise VoyageUnavailable(str(last)) from last

    async def embed_batch(
        self,
        texts: Sequence[str],
        collection: str,
        input_type: InputType,
        *,
        court_code: str | None = None,
    ) -> EmbeddingBatch:
        """Embed several texts in ONE request. `input_type` is required: "query" for
        a search query, "document" for text that will be stored and searched. For a
        collection embedded per court (A128), `court_code` names the court whose model
        is wanted; a court that is not registered is refused."""
        check_input_type(input_type)
        # raises before any request is sent
        model = self._s.embed_model_for(collection, court_code)
        if not texts:
            raise ValueError("nothing to embed")
        data = await self._post(
            "embeddings",
            {
                "input": list(texts),
                "model": model,
                "input_type": input_type,
                "output_dimension": DIM,
            },
        )
        rows = sorted(data["data"], key=lambda r: r.get("index", 0))
        vectors = [r["embedding"] for r in rows]
        if len(vectors) != len(texts):
            raise VoyageUnavailable(
                f"asked for {len(texts)} embeddings, got {len(vectors)}"
            )
        return EmbeddingBatch(vectors, int((data.get("usage") or {}).get("total_tokens", 0)))

    async def embed(
        self,
        text: str,
        collection: str,
        input_type: InputType,
        *,
        court_code: str | None = None,
    ) -> list[float]:
        batch = await self.embed_batch(
            [text], collection, input_type, court_code=court_code
        )
        return batch.vectors[0]

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
    """Deterministic hashed bag-of-words vector. `down=True` simulates an outage. A query
    and a document of the same text get DIFFERENT vectors (as with the real service), so a
    caller that picks the wrong input_type shows up in a test."""

    def __init__(self, dim: int = 64, down: bool = False):
        refuse_in_production()
        self.dim, self.down = dim, down
        self.calls = 0

    def _vector(self, text: str, input_type: InputType) -> list[float]:
        v = [0.0] * self.dim
        for w in words(text):
            h = int(hashlib.md5(w.encode(), usedforsecurity=False).hexdigest(), 16)
            v[h % self.dim] += 1.0
        salt = int(hashlib.md5(input_type.encode(), usedforsecurity=False).hexdigest(), 16)
        v[salt % self.dim] += 0.25
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    async def embed_batch(
        self,
        texts: Sequence[str],
        collection: str | None,
        input_type: InputType,
        *,
        court_code: str | None = None,
    ) -> EmbeddingBatch:
        check_input_type(input_type)
        self.calls += 1
        if self.down:
            raise VoyageUnavailable("fake down")
        return EmbeddingBatch(
            [self._vector(t, input_type) for t in texts],
            sum(max(1, len(t) // 4) for t in texts),
        )

    async def embed(
        self,
        text: str,
        collection: str | None,
        input_type: InputType,
        *,
        court_code: str | None = None,
    ) -> list[float]:
        batch = await self.embed_batch([text], collection, input_type)
        return batch.vectors[0]


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
