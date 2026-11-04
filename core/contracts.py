"""Shared types for the research pipeline (CLAUDE.md section 4).

Plain words: this file is the handshake between lanes. It says what goes into the
pipeline, what comes out, and what shape trust's gate and verifier must have. It has
no business logic and calls no outside service.

Everyone imports from here:  from core.contracts import PipelineRequest, run_pipeline

Key promises encoded in the types:
- A Citation can only be "verified" or "partly". An unverified citation is removed by
  the verifier and never reaches a user (CLAUDE.md section 5).
- show() only accepts a VerifiedAnswer, and only the verifier's seal_answer() can make
  one. So text cannot reach a user without passing the verifier.
- Passage counts are 50 -> 10 -> at most 8 (S1-S8). See the constants below.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

if TYPE_CHECKING:  # type-only imports: keep this file free of vendor code
    from adapters.cache import AnswerCache
    from adapters.decisions import DecisionService
    from adapters.llm import LLM
    from adapters.qdrant import VectorStore
    from adapters.voyage import Embedder, Reranker
    from core.settings import Settings

# --- Fixed numbers (changing these needs a docs/DECISIONS.md entry) ---------------
SEARCH_TOP_K = 50
RERANK_TOP_K = 10
GATE_MAX_PASSAGES = 8
MEMORY_FULL_TURNS = 6

# --- Vocabulary -------------------------------------------------------------------
Outcome = Literal["answered", "not_found", "out_of_scope", "usage_limit", "error"]
# "unchecked" = support not checked (Jev and Gemini both down): NO tick.
# "partly" = a real "partly" rating. A failed citation is removed, never a status.
CitationStatus = Literal["verified", "partly", "unchecked"]
PassageKind = Literal["judgment", "act_section", "upload"]
SafetyClass = Literal["normal", "personal_advice", "trick"]
ScopeClass = Literal[
    "in_scope",
    "needs_lower_court",
    "needs_tribunal",
    "after_snapshot",
    "not_in_dataset",  # a source the dataset does not hold (O7); not a court matter
    "not_legal",
]
Rating = Literal["answers", "partly", "not_relevant"]
Support = Literal["supports", "partly", "does_not_support"]
FailReason = Literal[
    "not_retrieved", "record_missing", "quote_not_found", "claim_not_supported"
]


# --- Matters and answer provenance (PRD-v2 O11, O12, O14) ---------------------------
MatterKind = Literal[
    "matter", "project"
]  # a label ("Matter" / "Project"), not a feature
MatterStatus = Literal["active", "archived"]


@dataclass(frozen=True)
class AnswerProvenance:
    """Did the user's own material shape this answer? Decided by the pipeline when the
    answer is produced and written to the database in step 11 (Save); never worked
    out later. Sharing (O14) reads it: shareable only if neither flag is set."""

    shaped_by_upload: bool = False
    shaped_by_matter_fact: bool = False

    @property
    def shareable(self) -> bool:
        return not (self.shaped_by_upload or self.shaped_by_matter_fact)


# --- Input -------------------------------------------------------------------------
@dataclass(frozen=True)
class Turn:
    role: Literal["user", "assistant"]
    text: str


@dataclass(frozen=True)
class PipelineRequest:
    user_id: str
    message: str
    conversation_id: str | None = None
    history: tuple[Turn, ...] = ()  # older turns; step 1 trims to the last 6
    summary: str = ""  # rolling summary of turns older than the last 6
    plan: Literal["free", "student", "pro", "chambers"] = "free"
    document_ids: tuple[str, ...] = ()  # non-empty = upload chat (never cached)
    # Remembered matter facts (client material, O12). Nothing fills this yet (memory is
    # not built); if it is ever non-empty the answer is flagged and never cached.
    matter_facts: tuple[str, ...] = ()


# --- Passages (the S1-S8 the model sees) --------------------------------------------
@dataclass(frozen=True)
class Passage:
    """One retrieved chunk. source_id is "" until the gate labels it S1..S8."""

    record_id: str  # id in kanoon_v1 (or user_documents); the verifier checks it
    text: str  # body text only (header already stripped)
    kind: PassageKind = "judgment"
    source_id: str = ""
    score: float = 0.0
    citation_string: str | None = None  # exactly as stored; never retyped
    # Two DERIVED identifiers for judgments with no stored citation
    # (core/hc_citation.py, A124). Kept apart from citation_string and from each other:
    # the verifier and the UI must tell a recorded citation from an extracted one from
    # a built label.
    neutral_citation: str | None = None  # published; from the judgment's own header
    case_reference: str | None = None  # a built description; NOT a citation
    pdf_url: str | None = None
    source_url: str | None = None
    title: str | None = None
    act_slug: str | None = None  # acts only
    section: str | None = None  # acts only
    anchor: str | None = None
    act_status: str | None = None  # show in-force flag only when filled
    page: int | None = None  # uploads only
    char_start: int | None = None
    char_end: int | None = None
    user_id: str | None = None  # uploads only
    case_id: str | None = None  # judgments only: the case this chunk belongs to


@dataclass(frozen=True)
class Filters:
    court: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    act: str | None = None
    section: str | None = None
    case_number: str | None = None
    # The year printed in the Act's own name ("1973" for the Code of Criminal
    # Procedure, 1973). It dates the Act, never judgments: core/decide.py keeps it
    # out of year_from/year_to.
    act_year: int | None = None

    @property
    def is_exact_lookup(self) -> bool:
        """Named section or case number: skip the merge, use a payload filter."""
        return bool(self.section or self.case_number)


# --- Step outputs ---------------------------------------------------------------------
@dataclass(frozen=True)
class Memory:  # step 1
    turns: tuple[Turn, ...]
    summary: str


@dataclass(frozen=True)
class RewrittenQuery:  # step 2
    query: str
    act: str | None = None
    section: str | None = None
    case_number: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class Decision:  # step 3
    scope: ScopeClass
    filters: Filters
    safety: SafetyClass
    note_ids: tuple[str, ...] = ()  # reviewed knowledge notes that apply
    jev_used: bool = True  # False when Gemini fallback decided

    @property
    def in_scope(self) -> bool:
        return self.scope == "in_scope"


@dataclass(frozen=True)
class GateResult:  # step 7 (written by trust)
    passages: tuple[Passage, ...]  # at most 8, labelled S1..S8, in order
    confidence: float
    ratings: dict[str, Rating] = field(default_factory=dict)  # record_id -> rating


@dataclass(frozen=True)
class DraftAnswer:  # step 8 output, step 9 input. NEVER shown to a user.
    text: str  # contains markers like [S1] after each sourced point
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    question: str = ""  # the rewritten question, for invented_citation_log


@dataclass(frozen=True)
class Citation:
    """A citation that survived verification. No "unverified" status exists."""

    source_id: str  # "S1".."S8"
    record_id: str
    status: CitationStatus
    citation_string: (
        str | None
    )  # exactly as recorded; label "as recorded in the dataset"
    pdf_url: str | None
    source_url: str | None
    title: str | None = None
    quote: str | None = None
    kind: Literal["judgment", "act"] = "judgment"
    anchor: str | None = None  # paragraph/page anchor when known
    act_slug: str | None = None  # acts only
    section: str | None = None  # acts only


@dataclass(frozen=True)
class RemovedCitation:  # goes to invented_citation_log, never to the user's screen
    source_id: str
    record_id: str | None
    reason: FailReason
    sentence: str = ""


@dataclass(frozen=True)
class VerifiedAnswer:  # step 9 output (written by trust)
    """Text with failed citations already removed.

    `_seal` is an HMAC over the content, made only by core/verify.py. Changing any
    field afterwards (dataclasses.replace, mutation) invalidates it. Always check with
    is_sealed(); never build one by hand.
    """

    text: str
    citations: tuple[Citation, ...]
    removed: tuple[RemovedCitation, ...] = ()
    _seal: bytes = field(default=b"", repr=False, compare=False)
    # A137: unmarked sentences the verifier dropped this turn. A count, never text.
    # Not in the seal (it carries no claim) and not cached: a cache hit ran no
    # verification.
    unmarked_removed: int = field(default=0, compare=False)

    @property
    def sealed(self) -> bool:
        return is_sealed(self)

    @property
    def had_removals(self) -> bool:
        return bool(self.removed)


_seal_checker: Callable[[VerifiedAnswer], bool] | None = None


def register_seal_checker(fn: Callable[[VerifiedAnswer], bool]) -> None:
    """core/verify.py calls this once at import. A second call is refused."""
    global _seal_checker
    if getattr(fn, "__module__", "") != "core.verify":
        raise RuntimeError("only core/verify.py may register the seal checker")
    if _seal_checker is not None:
        raise RuntimeError("seal checker already registered")
    _seal_checker = fn


def is_sealed(answer: object) -> bool:
    """True only for a VerifiedAnswer whose content matches its seal. If no verifier
    has registered a checker, nothing is sealed (fail closed)."""
    if not isinstance(answer, VerifiedAnswer) or _seal_checker is None:
        return False
    return _seal_checker(answer)


# --- Output ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Footer:
    """What every result carries (CLAUDE.md section 6); wording is UX copy."""

    data_as_of: str
    snapshot_version: str
    credit: str = ""  # filled from settings.DATA_CREDIT (CC BY 4.0 line)
    not_legal_advice: bool = True
    personal_advice_flag: bool = (
        False  # answer should open by declining personal advice
    )


@dataclass(frozen=True)
class PipelineResult:
    outcome: Outcome
    answer: VerifiedAnswer | None  # set only when outcome == "answered"
    footer: Footer
    message_key: str = ""  # for non-answers: "out_of_scope:not_in_dataset" etc.
    confidence: float | None = None
    cache_hit: bool = False  # hits are free and not counted against the limit
    counted: bool = False  # True when the usage meter counted one answer
    error: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    removed: tuple[RemovedCitation, ...] = ()
    provenance: AnswerProvenance = AnswerProvenance()

    def __post_init__(self) -> None:
        if self.outcome == "answered":
            if self.answer is None or not is_sealed(self.answer):
                raise ValueError("an answered result needs a sealed VerifiedAnswer")
        elif self.answer is not None:
            raise ValueError("only an answered result may carry an answer")


# Stream events (step 10). Text first; the checked citations arrive as ONE final event.
@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class FinalEvent:
    outcome: Outcome
    citations: tuple[Citation, ...]
    footer: Footer
    message_key: str = ""
    had_removals: bool = False


StreamEvent = TextDelta | FinalEvent


# Live progress (PRD-v2 section 4.2). A step event says WHICH step is running and
# HOW MANY passages there are. It can hold nothing else: no case name, citation,
# quote, record id or any text. Verified citations still arrive only as the ONE
# FinalEvent (step 10).
StepName = Literal["understanding", "searching", "checking", "writing", "verifying"]
STEP_NAMES: tuple[str, ...] = (
    "understanding",  # steps 1-3: remember, rewrite, decide
    "searching",  # steps 5-6: search, re-rank
    "checking",  # step 7: gate (found = passages the search returned)
    "writing",  # step 8: answer (found, kept = passages that survived the gate)
    "verifying",  # step 9: the citation verifier is running
)


@dataclass(frozen=True)
class StepEvent:
    step: StepName
    found: int | None = None
    kept: int | None = None

    def __post_init__(self) -> None:
        if self.step not in STEP_NAMES:
            raise ValueError(f"unknown step name: {self.step!r}")
        for n in (self.found, self.kept):
            # bool is an int subclass: refuse it too. Only counts, never text.
            bad_type = isinstance(n, bool) or not isinstance(n, int)
            if n is not None and (bad_type or n < 0):
                raise ValueError("a step event carries counts only")


OnStep = Callable[[StepEvent], None]


# --- Interfaces for steps owned by another lane ---------------------------------
class GateFn(Protocol):
    """Step 7, implemented in core/gate.py (trust)."""

    def __call__(
        self, query: RewrittenQuery, passages: Sequence[Passage], deps: Deps
    ) -> Awaitable[GateResult]: ...


class VerifyFn(Protocol):
    """Step 9, implemented in core/verify.py (trust). Must return a sealed answer
    and write removed citations to the log. Checks 1-3 run even if Jev is down."""

    def __call__(
        self,
        draft: DraftAnswer,
        passages: Sequence[Passage],
        deps: Deps,
    ) -> Awaitable[VerifiedAnswer]: ...


class UsageMeter(Protocol):
    async def allowed(self, user_id: str, plan: str) -> bool: ...
    async def count_one(self, user_id: str) -> None: ...


class CitationLog(Protocol):
    """Writes invented_citation_log rows (real one: PostgreSQL, platform)."""

    async def write(
        self, question: str, model: str, removed: Sequence[RemovedCitation]
    ) -> None: ...


class ConversationStore(Protocol):
    """Step 11 target. Real one is PostgreSQL (platform); fake in adapters/memory.py."""

    async def save(self, request: PipelineRequest, result: PipelineResult) -> None: ...


@dataclass
class Deps:
    """Everything the pipeline needs, passed in so tests can use fakes."""

    settings: Settings
    embedder: Embedder
    reranker: Reranker
    vectors: VectorStore
    llm: LLM
    decisions: DecisionService
    cache: AnswerCache
    usage: UsageMeter
    store: ConversationStore
    citation_log: CitationLog
    gate: GateFn
    verify: VerifyFn
    notes: Callable[[Sequence[str]], Sequence[str]] = lambda ids: ()  # reviewed notes
    # Called once at the start of every run. Platform passes adapters.jev.begin_run so
    # Jev batches stay inside one run; the default does nothing.
    begin_run: Callable[[], Any] = lambda: None


async def run_pipeline(
    request: PipelineRequest, deps: Deps, on_step: OnStep | None = None
) -> PipelineResult:
    """THE entry point. Runs steps 1-9 and 11; use stream_events() for step 10.
    `on_step` (optional) is told which step is running, with counts only."""
    from core.pipeline import run_pipeline as _run  # lazy: avoids an import cycle

    return await _run(request, deps, on_step)


def stream_events(result: PipelineResult) -> AsyncIterator[StreamEvent]:
    """Step 10: text word by word, then one FinalEvent with the checked citations."""
    from core.show import show

    return show(result)
