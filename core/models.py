"""Typed inputs and outputs for the 11 pipeline steps (CLAUDE.md rule 7).

Plain frozen dataclasses: each step takes some of these and returns one of these, so
any step can be swapped without touching the others. Nothing here has any logic.
There is deliberately NO field for judge or party names (CLAUDE.md section 6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from adapters.qdrant import SearchFilters

# ---- step 1: remember ----


@dataclass(frozen=True)
class Turn:
    """One exchange: what the user asked and what they were answered."""

    user: str
    assistant: str


@dataclass(frozen=True)
class Memory:
    recent: tuple[Turn, ...] = ()  # last 6 exchanges, in full
    summary: str = ""  # rolling summary of everything older


# ---- step 2: rewrite ----


@dataclass(frozen=True)
class RewriteResult:
    query: str  # one standalone question
    act_name: str = ""
    section: str = ""
    case_number: str = ""
    year: int | None = None


# ---- step 3: decide ----


@dataclass(frozen=True)
class DecideResult:
    scope: (
        str  # in_scope / needs_high_court / needs_tribunal / after_snapshot / not_legal
    )
    safety: str  # normal / personal_advice / trick
    filters: SearchFilters = field(default_factory=SearchFilters)
    note_ids: tuple[str, ...] = ()  # reviewed knowledge notes that apply
    jev_used: bool = False  # True if at least one decision really came from Jev
    degraded: bool = (
        False  # True if the decision service was down and defaults were used
    )


# ---- step 4: cache ----


@dataclass(frozen=True)
class CacheLookup:
    key: str
    hit: bool
    payload: dict | None = None


# ---- steps 5-6: search, rerank ----


@dataclass(frozen=True)
class SearchResult:
    hits: tuple  # tuple[adapters.qdrant.SearchHit, ...], best first, at most 50
    keyword_only: bool = False  # Voyage was down: meaning search skipped
    exact: bool = False  # came from an exact section / case-number lookup


@dataclass(frozen=True)
class RankedPassage:
    record_id: str
    chunk_id: str
    text: str
    rerank_score: float
    rank: int  # 1 = best


@dataclass(frozen=True)
class RerankResult:
    passages: tuple[RankedPassage, ...]  # at most 10
    used_fallback: bool = False  # Voyage was down: kept search order


# ---- step 7: gate ----


@dataclass(frozen=True)
class Source:
    """A passage that survived the gate and was shown to the model as S1..S8."""

    source_id: str
    record_id: str
    chunk_id: str
    text: str
    rank: int
    rerank_score: float
    relevance: str  # answers / partly (from the gate)
    relevance_confidence: float


@dataclass(frozen=True)
class GateResult:
    sources: tuple[Source, ...]  # empty means "not found"
    jev_used: bool = False

    @property
    def found(self) -> bool:
        return bool(self.sources)


# ---- step 8: answer ----


@dataclass(frozen=True)
class AnswerDraft:
    """What the model wrote. NOT safe to show: citations are unchecked."""

    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0


# ---- step 9: verify ----

CitationStatus = Literal["verified", "partly", "unchecked"]


@dataclass(frozen=True)
class CheckedCitation:
    """A citation that passed checks 1-3 (and 4, unless it could not run)."""

    source_id: str
    record_id: str
    sentence: str
    offset: int  # where in the clean answer text it attaches
    status: (
        CitationStatus  # verified=supports, partly=warning mark, unchecked=check 4 down
    )
    support_confidence: float = 0.0
    support_source: str = ""  # "jev" / "fallback" / "" if not run


@dataclass(frozen=True)
class RemovedCitation:
    source_id: str
    reason: str  # one of core.constants.REMOVAL_REASONS
    sentence: str


@dataclass(frozen=True)
class VerifiedAnswer:
    """Output of the verifier. Only core.verify can create a correctly *sealed* one (the
    seal is a keyed hash of the content), and show() refuses anything else - so no caller
    can skip verification or edit a verified answer afterwards."""

    text: str  # clean text: all citation markers stripped
    citations: tuple[CheckedCitation, ...]
    removed: tuple[RemovedCitation, ...]
    unverified_sentences: tuple[str, ...]
    total_cited: (
        int  # how many citations the model wrote (for the verified-citation rate)
    )
    _seal: str = field(default="", repr=False, compare=False)


# ---- step 10: show ----


@dataclass(frozen=True)
class CitationView:
    source_id: str
    record_id: str
    status: CitationStatus
    label: str
    title: str
    url: str
    offset: int
    citation_string: str = ""  # exactly as stored; "" for High Courts
    citation_string_label: str = ""
    in_force_label: str = ""  # Acts only


@dataclass(frozen=True)
class FinalAnswer:
    text: str
    citations: tuple[CitationView, ...]
    note: str  # "N authorities could not be verified..." or ""
    opening: str  # personal-advice opening, or ""
    notice: str  # not legal advice
    data_as_of: str
    credit: str


# ---- steps 1-11 together ----


@dataclass(frozen=True)
class PipelineRequest:
    user_id: str
    message: str
    history: tuple[Turn, ...] = ()
    summary: str = ""
    plan: str = "free"
    conversation_id: str = ""
    is_upload_chat: bool = False  # upload text never goes to Jev, never cached


Outcome = Literal[
    "answered", "out_of_scope", "blocked", "not_found", "llm_unavailable", "unavailable"
]


@dataclass(frozen=True)
class PipelineResult:
    outcome: Outcome
    message: str = ""  # user-facing text for every outcome except "answered"
    final: FinalAnswer | None = None
    memory: Memory = Memory()
    rewrite: RewriteResult | None = None
    decision: DecideResult | None = None
    sources: tuple[Source, ...] = ()
    from_cache: bool = False
    keyword_only: bool = False
    saved_message_id: str = ""
