"""Qdrant: the vector store. The ONLY file that talks to Qdrant.

Plain words: search the shared law collection, look a record up by id, and search the
private uploads collection. Uploads can ONLY be reached through search_uploads() and
get_record(..., user_id=...), and both always filter on user_id. Nothing else may build
an upload query (CLAUDE.md section 6; the shared wrapper is core/uploads.py).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from adapters.guard import refuse_in_production
from core.settings import Settings


class VectorStoreUnavailable(Exception):
    pass


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


class QdrantStore:
    """Real client (qdrant_client imported lazily). Dense search + payload filter
    only; the BM25 sparse half and RRF merge are NOT wired. Not verified."""

    def __init__(self, settings: Settings):
        self._s = settings
        self._client = None

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

    async def search(self, collection, vector, text, must, limit):
        if collection == self._s.QDRANT_UPLOADS_COLLECTION:
            raise PermissionError("uploads are reachable only via search_uploads")
        if vector is None:
            raise VectorStoreUnavailable("keyword-only search not wired yet")
        try:
            r = await self._c().query_points(
                collection,
                query=list(vector),
                query_filter=self._filter(must),
                limit=limit,
                with_payload=True,
            )
        except Exception as e:
            raise VectorStoreUnavailable(str(e)) from e
        return [self._hit(p) for p in r.points]

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
