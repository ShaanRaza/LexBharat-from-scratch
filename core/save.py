"""Step 11 - SAVE: message, source IDs, Jev decisions, model, token counts, removed
citations, and the cache entry. The usage meter counts one answer unless it came from
the cache.

The database itself belongs to the api/ lane (Alembic + SQLAlchemy). This file only
defines the `MessageRepository` interface it must implement, plus an in-memory version
for tests. Row fields follow docs/DATA-MODEL.md (messages, message_sources,
invented_citation_log).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from adapters.cache import AnswerCache
from core.models import (
    AnswerDraft,
    DecideResult,
    FinalAnswer,
    PipelineRequest,
    RewriteResult,
    Source,
    VerifiedAnswer,
)
from core.settings import Settings


@dataclass(frozen=True)
class SavedSource:
    source_id: str
    record_id: str
    chunk_id: str
    rank: int
    rerank_score: float
    relevance: str
    verified: bool  # True only if the citation to it passed (status verified/partly)
    support: str  # supports / partly / "" (not checked or not cited)
    support_confidence: float


@dataclass(frozen=True)
class SavedMessage:
    user_id: str
    conversation_id: str
    content: str
    rewritten_query: str
    model: str
    tokens_in: int
    tokens_out: int
    scope: str
    safety: str
    jev_used: bool
    from_cache: bool
    counts_against_limit: bool  # the usage meter: cache hits are free
    sources: tuple[SavedSource, ...]


@dataclass(frozen=True)
class InventedCitationRow:
    query: str
    model: str
    cited_text: str
    reason: (
        str  # not_retrieved / record_missing / quote_not_found / claim_not_supported
    )


class MessageRepository(Protocol):
    async def save_message(self, message: SavedMessage) -> str: ...
    async def log_invented_citations(
        self, message_id: str, rows: list[InventedCitationRow]
    ) -> None: ...


@dataclass
class InMemoryMessageRepository:
    messages: list[SavedMessage] = field(default_factory=list)
    invented: list[tuple[str, InventedCitationRow]] = field(default_factory=list)

    async def save_message(self, message: SavedMessage) -> str:
        self.messages.append(message)
        return f"msg_{len(self.messages)}"

    async def log_invented_citations(
        self, message_id: str, rows: list[InventedCitationRow]
    ) -> None:
        self.invented.extend((message_id, r) for r in rows)


async def save(
    request: PipelineRequest,
    rewrite: RewriteResult,
    decision: DecideResult,
    sources: tuple[Source, ...],
    draft: AnswerDraft,
    verified: VerifiedAnswer,
    final: FinalAnswer,
    repo: MessageRepository,
    cache: AnswerCache,
    cache_key: str,
    settings: Settings,
    *,
    from_cache: bool,
    jev_used: bool,
) -> str:
    support = {c.source_id: c for c in verified.citations}
    saved_sources = tuple(
        SavedSource(
            source_id=s.source_id,
            record_id=s.record_id,
            chunk_id=s.chunk_id,
            rank=s.rank,
            rerank_score=s.rerank_score,
            relevance=s.relevance,
            verified=s.source_id in support,
            support={"verified": "supports", "partly": "partly"}.get(
                support[s.source_id].status, ""
            )
            if s.source_id in support
            else "",
            support_confidence=support[s.source_id].support_confidence
            if s.source_id in support
            else 0.0,
        )
        for s in sources
    )
    message_id = await repo.save_message(
        SavedMessage(
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            content=final.text,
            rewritten_query=rewrite.query,
            model=draft.model,
            tokens_in=draft.tokens_in,
            tokens_out=draft.tokens_out,
            scope=decision.scope,
            safety=decision.safety,
            jev_used=jev_used or decision.jev_used,
            from_cache=from_cache,
            counts_against_limit=not from_cache,
            sources=saved_sources,
        )
    )
    if verified.removed:
        await repo.log_invented_citations(
            message_id,
            [
                InventedCitationRow(
                    query=rewrite.query,
                    model=draft.model,
                    cited_text=f"{r.source_id}: {r.sentence}",
                    reason=r.reason,
                )
                for r in verified.removed
            ],
        )
    # Cache only clean, non-upload answers: nothing removed, nothing left unchecked.
    clean = not verified.removed and all(
        c.status != "unchecked" for c in verified.citations
    )
    if clean and not request.is_upload_chat and not from_cache:
        await cache.set(
            cache_key,
            {
                "draft_text": draft.text,
                "model": draft.model,
                "tokens_in": draft.tokens_in,
                "tokens_out": draft.tokens_out,
                "sources": [s.__dict__ for s in sources],
            },
            settings.ANSWER_CACHE_TTL_DAYS,
        )
    return message_id
