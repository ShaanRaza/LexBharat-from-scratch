"""Qdrant adapter: the search index (`kanoon_v1`) and the records behind it.

Rule 1: the ONLY file that talks to Qdrant. Collection names come from settings
(QDRANT_COLLECTION, QDRANT_UPLOADS_COLLECTION), never from code.

Pipeline steps that use it:
  5 Search   -> search_hybrid / search_keyword / exact_lookup
  9 Verify   -> get_record  (check 2: "the record exists")

Two privacy/trust rules are built into the interface:
  - `Record` has NO judge or party-name fields. They are unreliable (CLAUDE.md s.6) so
    they are never carried through the code, which makes them impossible to display.
  - `search_user_documents` REQUIRES a user_id and refuses an empty one. This is the
    single shared data-access function for uploads; no other code queries that
    collection.

Only the interface and a Fake live here; no real network calls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True)
class Record:
    """One record in the corpus (a judgment or one Act section)."""

    record_id: str
    source_type: Literal["judgment", "act"]
    title: str
    text: str  # full text; check 3 looks for quoted words in here
    court: str = ""
    year: int | None = None
    citation: str = ""  # shown exactly as stored, never retyped (empty for High Courts)
    case_number: str = ""
    pdf_url: str = ""  # judgments
    source_url: str = ""  # Acts
    act_name: str = ""
    section_number: str = ""
    act_status: str = ""  # only filled for 1,568 of 22,264 acts


@dataclass(frozen=True)
class SearchFilters:
    """Payload filters (docs/DATA-MODEL.md). Empty means "no filter on this"."""

    court: str = ""
    year_from: int | None = None
    year_to: int | None = None
    act_name: str = ""
    section_number: str = ""
    case_number: str = ""
    source_type: str = ""

    def is_exact_lookup(self) -> bool:
        """A named section or case number skips the merge and goes to exact filters."""
        return bool(self.case_number or (self.act_name and self.section_number))


@dataclass(frozen=True)
class SearchHit:
    """One chunk found by search. `record_id` points at the full Record."""

    record_id: str
    chunk_id: str
    text: str
    score: float


class VectorStore(Protocol):
    async def search_hybrid(
        self, vector: list[float], query: str, filters: SearchFilters, limit: int
    ) -> list[SearchHit]: ...

    async def search_keyword(
        self, query: str, filters: SearchFilters, limit: int
    ) -> list[SearchHit]: ...

    async def exact_lookup(
        self, filters: SearchFilters, limit: int
    ) -> list[SearchHit]: ...

    async def get_record(self, record_id: str) -> Record | None: ...

    async def search_user_documents(
        self, *, user_id: str, vector: list[float], limit: int
    ) -> list[SearchHit]: ...


_WORD = re.compile(r"\w+", re.UNICODE)


def _words(text: str) -> set[str]:
    return {w.casefold() for w in _WORD.findall(text)}


def _passes(record: Record, f: SearchFilters) -> bool:
    if f.court and record.court != f.court:
        return False
    if f.year_from and (record.year is None or record.year < f.year_from):
        return False
    if f.year_to and (record.year is None or record.year > f.year_to):
        return False
    return not (f.source_type and record.source_type != f.source_type)


@dataclass
class FakeVectorStore:
    """In-memory corpus for tests.

    `add_record(record)` stores a record and one chunk with the record's text.
    `add_chunk(record_id, chunk_id, text)` adds extra chunks.
    `hide_record(record_id)` removes the record but keeps its chunks, to simulate a
    search index that points at a record that no longer exists (check 2 must catch it).
    Every user-document query is logged in `.upload_queries` so tests can assert the
    user_id filter was always present.
    """

    records: dict[str, Record] = field(default_factory=dict)
    chunks: list[tuple[str, str, str]] = field(default_factory=list)  # rec, chunk, text
    uploads: list[tuple[str, str, str]] = field(
        default_factory=list
    )  # user, chunk, text
    upload_queries: list[str] = field(default_factory=list)

    def add_record(self, record: Record) -> None:
        self.records[record.record_id] = record
        self.chunks.append((record.record_id, f"{record.record_id}#0", record.text))

    def add_chunk(self, record_id: str, chunk_id: str, text: str) -> None:
        self.chunks.append((record_id, chunk_id, text))

    def hide_record(self, record_id: str) -> None:
        self.records.pop(record_id, None)

    def add_upload_chunk(self, user_id: str, chunk_id: str, text: str) -> None:
        self.uploads.append((user_id, chunk_id, text))

    def _score(self, query: str, filters: SearchFilters, limit: int) -> list[SearchHit]:
        q = _words(query)
        hits = []
        for rec_id, chunk_id, text in self.chunks:
            record = self.records.get(rec_id)
            if record is not None and not _passes(record, filters):
                continue
            score = len(q & _words(text)) / (len(q) or 1)
            if score > 0:
                hits.append(SearchHit(rec_id, chunk_id, text, score))
        hits.sort(key=lambda h: -h.score)
        return hits[:limit]

    async def search_hybrid(
        self, vector: list[float], query: str, filters: SearchFilters, limit: int
    ) -> list[SearchHit]:
        assert vector, "hybrid search needs a query vector"
        return self._score(query, filters, limit)

    async def search_keyword(
        self, query: str, filters: SearchFilters, limit: int
    ) -> list[SearchHit]:
        return self._score(query, filters, limit)

    async def exact_lookup(self, filters: SearchFilters, limit: int) -> list[SearchHit]:
        hits = []
        for rec_id, chunk_id, text in self.chunks:
            r = self.records.get(rec_id)
            if r is None or not _passes(r, filters):
                continue
            if filters.case_number and r.case_number != filters.case_number:
                continue
            if (
                filters.act_name
                and r.act_name.casefold() != filters.act_name.casefold()
            ):
                continue
            if filters.section_number and r.section_number != filters.section_number:
                continue
            hits.append(SearchHit(rec_id, chunk_id, text, 1.0))
        return hits[:limit]

    async def get_record(self, record_id: str) -> Record | None:
        return self.records.get(record_id)

    async def search_user_documents(
        self, *, user_id: str, vector: list[float], limit: int
    ) -> list[SearchHit]:
        if not user_id:
            raise ValueError("user_id is required for every upload query")
        self.upload_queries.append(user_id)
        return [
            SearchHit("", chunk_id, text, 1.0)
            for uid, chunk_id, text in self.uploads
            if uid == user_id
        ][:limit]
