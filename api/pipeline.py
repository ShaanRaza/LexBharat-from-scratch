"""The contract between the API and the research pipeline (which lives in core/).

Routes hold no business logic (rule: api/ is routes only). The 11-step pipeline is the
Core agent's work, so the API talks to it through the small interface below, and a test
double implements it. Wiring the real pipeline = one class that satisfies
`ResearchPipeline`, set on `app.state.pipeline` (see api/deps.py).

Streaming contract (docs/API.md): the pipeline yields `TextDelta`s as the answer is
written, then exactly ONE `FinalAnswer` after the citation verifier has run.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass
class HistoryTurn:
    role: Literal["user", "assistant"]
    content: str


@dataclass
class TextDelta:
    """A few words of answer text. Must not contain citation markers like [S1]."""

    text: str


@dataclass
class VerifiedCitation:
    """One citation that already passed the verifier (checks 1-4)."""

    source_id: str  # "S1".."S8"
    record_id: str
    title: str | None
    citation: str | None  # the stored citation string, exactly as recorded
    url: str | None  # pdf_url or source_url
    # "verified" = tick, "partly" = warning mark. Failed citations never get here.
    status: Literal["verified", "partly"]


@dataclass
class RemovedCitation:
    cited_text: str
    reason: Literal[
        "not_retrieved", "record_missing", "quote_not_found", "claim_not_supported"
    ]


@dataclass
class SourceRow:
    """What gets saved to message_sources for the audit trail."""

    source_id: str
    record_id: str
    chunk_id: str | None = None
    rank: int | None = None
    rerank_score: float | None = None
    verified: bool = False
    relevance: str | None = None
    support: str | None = None
    support_confidence: float | None = None


@dataclass
class FinalAnswer:
    text: str  # the full text after verification
    outcome: Literal["answered", "not_found", "out_of_scope"] = "answered"
    citations: list[VerifiedCitation] = field(default_factory=list)
    removed: list[RemovedCitation] = field(default_factory=list)
    sources: list[SourceRow] = field(default_factory=list)
    data_as_of: str | None = None
    # Step 11 (Save) details:
    rewritten_query: str | None = None
    model: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    latency_ms: int | None = None
    from_cache: bool = False
    scope: str | None = None
    route: str | None = None
    safety: str | None = None
    jev_used: bool = False
    rolling_summary: str | None = None


@dataclass
class SearchHit:
    record_id: str
    title: str | None
    snippet: str | None
    url: str | None
    court: str | None = None
    year: int | None = None


class ResearchPipeline(Protocol):
    def answer(
        self,
        *,
        user_id: str,
        question: str,
        history: list[HistoryTurn],
        rolling_summary: str | None,
    ) -> AsyncIterator[TextDelta | FinalAnswer]: ...

    async def search(
        self, *, query: str, filters: dict[str, Any], limit: int
    ) -> list[SearchHit]: ...
