"""Qdrant: the vector store. The ONLY file that talks to Qdrant.

Plain words: search the shared law collection, look a record up by id, and search the
private uploads collection. Uploads can ONLY be reached through search_uploads() and
get_record(..., user_id=...), and both always filter on user_id. Nothing else may build
an upload query (CLAUDE.md section 6; the shared wrapper is core/uploads.py).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from adapters.guard import refuse_in_production
from core import coverage
from core.settings import Settings


class VectorStoreUnavailable(Exception):
    pass


# Names of the two vectors stored on every point of the law collections (Measured on
# the local copy, see docs/DATASET.md).
DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"

# English judgments are selected by the court payload field (value from the coverage
# source). `language_code` is mostly missing and uses uppercase "EN" (Measured), so
# filtering on it silently drops real chunks.
# Payload keys that mean "the user named this exactly": they skip the merge.
EXACT_KEYS = ("section_number", "case_number")

# text -> (sparse indices, sparse values), QUERY side.
SparseEncoder = Callable[[str], tuple[list[int], list[float]]]


def english_supreme_court() -> dict[str, str]:
    """The payload filter that selects the English judgments the coverage source
    lists (today one court). The name is read from core/coverage.json, not typed."""
    return coverage.court_payload("supreme_court")


class FastEmbedBm25:
    """Keyword half of the search: FastEmbed `Qdrant/bm25`. The sparse vectors in the
    collection were built with it, so queries must use query_embed(), NOT embed()
    (embed() is the document side and weights terms differently). Loaded on first use
    so importing this file stays cheap; fastembed is the optional `search` extra."""

    def __init__(self) -> None:
        self._model = None

    def __call__(self, text: str) -> tuple[list[int], list[float]]:
        if self._model is None:
            try:
                from fastembed import SparseTextEmbedding
            except ImportError as e:
                raise VectorStoreUnavailable(
                    "fastembed is not installed (pip install '.[search]')"
                ) from e
            self._model = SparseTextEmbedding(model_name="Qdrant/bm25")
        emb = next(iter(self._model.query_embed([text])))
        return [int(i) for i in emb.indices], [float(v) for v in emb.values]


@dataclass(frozen=True)
class Hit:
    record_id: str
    text: str  # body text (header stripped)
    score: float = 0.0
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecordText:
    record_id: str
    text: str
    payload: Mapping[str, Any] = field(default_factory=dict)


class VectorStore(Protocol):
    async def search(
        self,
        collection: str,
        vector: Sequence[float] | None,
        text: str,
        must: Mapping[str, Any],
        limit: int,
    ) -> list[Hit]:
        """Law collection only. vector=None means keyword-only (Voyage down).
        `must` is an exact payload filter; a non-empty must on section/case number is
        the exact-lookup path."""
        ...

    async def search_uploads(
        self,
        user_id: str,
        vector: Sequence[float] | None,
        text: str,
        document_ids: Sequence[str],
        limit: int,
    ) -> list[Hit]: ...

    async def get_record(
        self, collection: str, record_id: str, user_id: str | None = None
    ) -> RecordText | None:
        """None = no such record. Upload records need user_id and are never returned
        to another user."""
        ...

    async def delete_upload_vectors(self, user_id: str, document_id: str) -> None:
        """Hard delete: every vector of this document (matched on BOTH user_id and
        document_id). Only core/uploads.py may call this."""
        ...

    async def count_upload_vectors(self, user_id: str, document_id: str) -> int:
        """How many vectors this document still has (the leftover check)."""
        ...


class _Points:
    """Gives scroll() results the same `.points` shape as query_points()."""

    def __init__(self, points):
        self.points = points


class QdrantStore:
    """Real client (qdrant_client imported lazily).

    Law search (pipeline step 5) is hybrid: a dense query (the Voyage vector passed in)
    and a keyword query (BM25, encoded here) run in ONE Qdrant call and are merged by
    Reciprocal Rank Fusion (RRF: a document ranked high by either half rises). A named
    section or case number skips the merge and goes to an exact payload filter.
    Voyage down (vector=None) runs the keyword half alone. Not verified against a live
    Qdrant: tests use a fake client."""

    def __init__(
        self,
        settings: Settings,
        sparse_encoder: SparseEncoder | None = None,
        client: Any = None,
    ):
        self._s = settings
        self._client = client
        self._encode = sparse_encoder or FastEmbedBm25()

    def _c(self):
        if self._client is None:
            from qdrant_client import AsyncQdrantClient

            self._client = AsyncQdrantClient(
                url=self._s.QDRANT_URL,
                api_key=self._s.QDRANT_API_KEY.get_secret_value() or None,
                timeout=5,
            )
        return self._client

    @staticmethod
    def _filter(must: Mapping[str, Any]):
        from qdrant_client import models

        return models.Filter(
            must=[
                models.FieldCondition(key=k, match=models.MatchValue(value=v))
                for k, v in must.items()
            ]
        )

    @staticmethod
    def _hit(p) -> Hit:
        pay = dict(p.payload or {})
        return Hit(
            str(pay.get("chunk_id", p.id)),
            pay.get("text", ""),
            getattr(p, "score", 0.0) or 0.0,
            pay,
        )

    async def _sparse_query(self, text: str):
        from qdrant_client import models

        # BM25 encoding is CPU work: keep it off the event loop.
        indices, values = await asyncio.to_thread(self._encode, text)
        return models.SparseVector(indices=indices, values=values)

    async def search(self, collection, vector, text, must, limit):
        if collection == self._s.QDRANT_UPLOADS_COLLECTION:
            raise PermissionError("uploads are reachable only via search_uploads")
        if "language_code" in must:
            raise ValueError(
                "do not filter on language_code (mostly missing, uppercase 'EN'); "
                "use court, e.g. english_supreme_court()"
            )
        from qdrant_client import models

        flt = self._filter(must)
        try:
            if any(k in must for k in EXACT_KEYS):
                r = await self._exact(collection, vector, flt, limit)
            else:
                prefetch = []
                if vector is not None:
                    prefetch.append(
                        models.Prefetch(
                            query=list(vector),
                            using=DENSE_VECTOR,
                            filter=flt,
                            limit=limit,
                        )
                    )
                prefetch.append(
                    models.Prefetch(
                        query=await self._sparse_query(text),
                        using=SPARSE_VECTOR,
                        filter=flt,
                        limit=limit,
                    )
                )
                r = await self._c().query_points(
                    collection,
                    prefetch=prefetch,
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    limit=limit,
                    with_payload=True,
                )
        except VectorStoreUnavailable:
            raise
        except Exception as e:
            raise VectorStoreUnavailable(str(e)) from e
        return [self._hit(p) for p in r.points]

    async def _exact(self, collection, vector, flt, limit):
        """Named section / case number: exact payload filter, no merge. Ranked by the
        dense vector when we have one, otherwise in stored order."""
        if vector is not None:
            return await self._c().query_points(
                collection,
                query=list(vector),
                using=DENSE_VECTOR,
                query_filter=flt,
                limit=limit,
                with_payload=True,
            )
        pts, _ = await self._c().scroll(
            collection, scroll_filter=flt, limit=limit, with_payload=True
        )
        return _Points(pts)

    async def search_uploads(self, user_id, vector, text, document_ids, limit):
        if not user_id:
            raise PermissionError("user_id is required for upload queries")
        if vector is None:
            raise VectorStoreUnavailable("keyword-only search not wired yet")
        from qdrant_client import models

        conds = [
            models.FieldCondition(key="user_id", match=models.MatchValue(value=user_id))
        ]
        if document_ids:
            conds.append(
                models.FieldCondition(
                    key="document_id", match=models.MatchAny(any=list(document_ids))
                )
            )
        try:
            r = await self._c().query_points(
                self._s.QDRANT_UPLOADS_COLLECTION,
                query=list(vector),
                query_filter=models.Filter(must=conds),
                limit=limit,
                with_payload=True,
            )
        except Exception as e:
            raise VectorStoreUnavailable(str(e)) from e
        return [self._hit(p) for p in r.points]

    def _doc_filter(self, user_id: str, document_id: str):
        from qdrant_client import models

        return models.Filter(
            must=[
                models.FieldCondition(
                    key="user_id", match=models.MatchValue(value=user_id)
                ),
                models.FieldCondition(
                    key="document_id", match=models.MatchValue(value=document_id)
                ),
            ]
        )

    async def delete_upload_vectors(self, user_id, document_id):
        if not user_id or not document_id:
            raise PermissionError("user_id and document_id are required")
        from qdrant_client import models

        try:
            await self._c().delete(
                self._s.QDRANT_UPLOADS_COLLECTION,
                points_selector=models.FilterSelector(
                    filter=self._doc_filter(user_id, document_id)
                ),
                wait=True,
            )
        except Exception as e:
            raise VectorStoreUnavailable(str(e)) from e

    async def count_upload_vectors(self, user_id, document_id):
        if not user_id or not document_id:
            raise PermissionError("user_id and document_id are required")
        try:
            r = await self._c().count(
                self._s.QDRANT_UPLOADS_COLLECTION,
                count_filter=self._doc_filter(user_id, document_id),
                exact=True,
            )
        except Exception as e:
            raise VectorStoreUnavailable(str(e)) from e
        return int(r.count)

    async def get_record(self, collection, record_id, user_id=None):
        is_upload = collection == self._s.QDRANT_UPLOADS_COLLECTION
        if is_upload and not user_id:
            raise PermissionError("user_id is required for upload records")
        must: dict[str, Any] = {"chunk_id": record_id}
        if is_upload:
            must["user_id"] = user_id
        try:
            pts, _ = await self._c().scroll(
                collection, scroll_filter=self._filter(must), limit=1, with_payload=True
            )
        except Exception as e:
            raise VectorStoreUnavailable(str(e)) from e
        if not pts:
            return None
        h = self._hit(pts[0])
        return RecordText(h.record_id, h.text, h.payload)


class FakeVectorStore:
    """In-memory store. Keyword-overlap scoring; ignores the vector. `down=True`
    simulates an outage. Records are dicts with payload fields."""

    def __init__(self, settings: Settings, down: bool = False):
        refuse_in_production()
        self._s, self.down = settings, down
        self.law: list[Hit] = []
        self.uploads: list[Hit] = []  # payload must contain user_id, document_id
        self.upload_queries: list[dict] = []  # audit trail for tests

    def add_law(self, record_id: str, text: str, **payload: Any) -> None:
        self.law.append(Hit(record_id, text, 0.0, {"chunk_id": record_id, **payload}))

    def add_upload(
        self, record_id: str, text: str, user_id: str, document_id: str, **payload: Any
    ) -> None:
        self.uploads.append(
            Hit(
                record_id,
                text,
                0.0,
                {
                    "chunk_id": record_id,
                    "user_id": user_id,
                    "document_id": document_id,
                    **payload,
                },
            )
        )

    def _check(self) -> None:
        if self.down:
            raise VectorStoreUnavailable("fake down")

    @staticmethod
    def _rank(pool: list[Hit], text: str, limit: int) -> list[Hit]:
        from adapters.voyage import words

        q = set(words(text))
        out = [
            Hit(
                h.record_id,
                h.text,
                len(q & set(words(h.text))) / (len(q) or 1),
                h.payload,
            )
            for h in pool
        ]
        out.sort(key=lambda h: (-h.score, h.record_id))
        return out[:limit]

    async def search(self, collection, vector, text, must, limit):
        self._check()
        if collection == self._s.QDRANT_UPLOADS_COLLECTION:
            raise PermissionError("uploads are reachable only via search_uploads")
        pool = [
            h for h in self.law if all(h.payload.get(k) == v for k, v in must.items())
        ]
        return self._rank(pool, text, limit)

    async def search_uploads(self, user_id, vector, text, document_ids, limit):
        self._check()
        if not user_id:
            raise PermissionError("user_id is required for upload queries")
        self.upload_queries.append(
            {"user_id": user_id, "document_ids": tuple(document_ids)}
        )
        pool = [
            h
            for h in self.uploads
            if h.payload["user_id"] == user_id
            and (not document_ids or h.payload["document_id"] in document_ids)
        ]
        return self._rank(pool, text, limit)

    async def delete_upload_vectors(self, user_id, document_id):
        self._check()
        if not user_id or not document_id:
            raise PermissionError("user_id and document_id are required")
        self.uploads = [
            h
            for h in self.uploads
            if not (
                h.payload["user_id"] == user_id
                and h.payload["document_id"] == document_id
            )
        ]

    async def count_upload_vectors(self, user_id, document_id):
        self._check()
        if not user_id or not document_id:
            raise PermissionError("user_id and document_id are required")
        return sum(
            1
            for h in self.uploads
            if h.payload["user_id"] == user_id
            and h.payload["document_id"] == document_id
        )

    async def get_record(self, collection, record_id, user_id=None):
        self._check()
        if collection == self._s.QDRANT_UPLOADS_COLLECTION:
            if not user_id:
                raise PermissionError("user_id is required for upload records")
            pool = [h for h in self.uploads if h.payload["user_id"] == user_id]
        else:
            pool = self.law
        for h in pool:
            if h.record_id == record_id:
                return RecordText(h.record_id, h.text, h.payload)
        return None
