"""Request and response shapes for the public API (docs/API.md).

This file is the contract the website's generated client is built from. It holds
shapes only: no business logic, no vendor imports (rule 3: web talks to api only
through the API).

Pipeline step 10 (Show) lives here: the streaming events at the bottom. The one
rule that matters most: exactly ONE `citations` event per answer, sent after
verification. Nothing citation-shaped is sent before it.

Never add judge or party-name fields: the dataset audit found them unreliable
(CLAUDE.md section 6).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- errors

ErrorCode = Literal[
    "unauthenticated",  # no / invalid / unverifiable Firebase token (HTTP 401)
    "forbidden",
    "not_found",
    "validation_error",
    "quota_exceeded",
    "rate_limited",
    "out_of_scope",  # step 3: question outside v1 coverage
    "not_found_in_dataset",  # step 7: nothing cleared the gate, nothing written
    "feature_disabled",  # e.g. uploads switch is off
    "service_unavailable",
    "internal_error",
]


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    """The one error format. Nothing else is ever returned."""

    error: ErrorBody


# ---------------------------------------------------------------- shared

# Wording shown to users. Shown once per response, never per sentence.
CC_BY_CREDIT = "Data: Open India Law by Vaquill AI, CC BY 4.0"
NOT_LEGAL_ADVICE = "This is legal research, not legal advice."


class Page(BaseModel):
    """Cursor pagination wrapper fields (every list uses these)."""

    next_cursor: str | None = None


class Provenance(BaseModel):
    """Attached to every result, stats page and Act page."""

    data_as_of: str = Field(description="Snapshot date, e.g. 2026-08-31")
    snapshot_version: str = Field(description="e.g. v2026.08")
    credit: str = CC_BY_CREDIT
    notice: str = NOT_LEGAL_ADVICE


# ---------------------------------------------------------------- /me

Plan = Literal["free", "student", "pro", "chambers"]
Role = Literal["advocate", "student", "in-house", "other"]


class MeResponse(BaseModel):
    id: UUID
    email: str | None = None
    name: str | None = None
    role: Role | None = None
    plan: Plan
    answers_left_this_month: int | None = Field(
        default=None, description="None means the limit is not configured yet"
    )


class ConsentOut(BaseModel):
    id: UUID
    notice_version: str
    purpose: str
    given_at: datetime
    withdrawn_at: datetime | None = None


class ConsentList(BaseModel):
    items: list[ConsentOut]


class ConsentIn(BaseModel):
    notice_version: str
    purpose: str


class ConsentWithdraw(BaseModel):
    consent_id: UUID


# ---------------------------------------------------------------- citations

CitationKind = Literal["judgment", "act"]
# Only "verified" shows a tick. "partly" (a real partly rating) shows a warning mark.
# "unchecked" (Jev and Gemini both down) shows the label "Support not checked" and NO
# tick: checks 1-3 passed, claim support was not rated. A failed citation is removed,
# never shown.
CitationStatus = Literal["verified", "partly", "unchecked"]


class Citation(BaseModel):
    """One checked citation. Tick is per citation, never one badge per answer.

    Tick wording in the UI: "Record found in dataset". It does NOT mean good law.
    """

    source_id: str = Field(pattern=r"^S[1-8]$", description="Label used in the text")
    kind: CitationKind
    # For a judgment: the record id of the case, and the paragraph anchor to jump to.
    # For an act: act_slug + section identify it.
    anchor: str | None = Field(
        default=None, description="Paragraph / passage anchor inside the record"
    )
    act_slug: str | None = Field(default=None, description="Acts only")
    section: str | None = Field(default=None, description="Acts only, e.g. '302'")
    record_id: str
    title: str | None = Field(
        default=None, description="Case title or Act name. Never judges or parties."
    )
    # Stored citation string, exactly as recorded. Never retyped by the AI.
    # None for records from courts whose citation strings are not in the dataset.
    citation_string: str | None = Field(
        default=None, description="Shown as 'as recorded in the dataset'"
    )
    url: str | None = Field(
        default=None, description="pdf_url or source_url of the record, if any"
    )
    status: CitationStatus


class CitationsEvent(BaseModel):
    """The ONE final citations event, sent after verification (step 9 -> 10)."""

    citations: list[Citation]
    removed_count: int = Field(
        default=0,
        description="Citations that failed verification and were removed; "
        "if > 0 the UI notes that one authority could not be verified",
    )
    data_as_of: str
    credit: str = CC_BY_CREDIT
    notice: str = NOT_LEGAL_ADVICE


# ---------------------------------------------------------------- SSE events


class TokenEvent(BaseModel):
    """A piece of answer text. May contain source labels like [S1] but carries no
    verification status: statuses only arrive in the citations event."""

    text: str


class StepEvent(BaseModel):
    """Live progress. Step name and counts ONLY: never a case name, citation, quote or
    record id. Sent before any token; the checked citations still arrive as the one
    `citations` event after verification."""

    step: Literal["understanding", "searching", "checking", "writing", "verifying"]
    found: int | None = Field(default=None, ge=0)
    kept: int | None = Field(default=None, ge=0)


class DoneEvent(BaseModel):
    message_id: UUID | None = None
    from_cache: bool = False
    reason: Literal["out_of_scope", "not_found"] | None = Field(
        default=None,
        description="Set when refused. Usage limit is NOT here: it arrives as an "
        "error event with code quota_exceeded.",
    )
    message_key: str | None = Field(
        default=None,
        description="Set when refused: key into docs/UX-COPY.md, e.g. "
        "'out_of_scope:needs_high_court' or 'not_found'. The website owns the wording.",
    )
    refused: bool = Field(
        default=False,
        description="True when out of scope or nothing found; no answer was written",
    )


class ErrorEvent(BaseModel):
    code: ErrorCode
    message: str
    request_id: str


class SSETokenFrame(BaseModel):
    event: Literal["token"] = "token"
    data: TokenEvent


class SSEStepFrame(BaseModel):
    event: Literal["step"] = "step"
    data: StepEvent


class SSECitationsFrame(BaseModel):
    event: Literal["citations"] = "citations"
    data: CitationsEvent


class SSEDoneFrame(BaseModel):
    event: Literal["done"] = "done"
    data: DoneEvent


class SSEErrorFrame(BaseModel):
    event: Literal["error"] = "error"
    data: ErrorEvent


SSEFrame = Annotated[
    SSEStepFrame | SSETokenFrame | SSECitationsFrame | SSEDoneFrame | SSEErrorFrame,
    Field(discriminator="event"),
]
"""Order on the wire: step* , token* , citations (exactly once, unless refused or
error), done. Step events all arrive before the first token. After an `error` event
the stream ends with no `done`."""

# ---------------------------------------------------------------- conversations

Module = Literal["research", "document"]


class ConversationCreate(BaseModel):
    module: Module = "research"
    document_id: UUID | None = None
    matter_id: UUID | None = None


class ConversationOut(BaseModel):
    id: UUID
    module: Module
    title: str | None = None
    message_count: int = 0
    document_id: UUID | None = None
    matter_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ConversationList(Page):
    items: list[ConversationOut]


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


# ---------------------------------------------------------------- matters, provenance

MatterKind = Literal["matter", "project"]  # the screen says "Matter" or "Project"
MatterStatus = Literal["active", "archived"]


class MatterCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    kind: MatterKind = "matter"


class MatterUpdate(BaseModel):
    """Rename and/or archive. At least one field."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: MatterStatus | None = None


class MatterOut(BaseModel):
    id: UUID
    title: str
    kind: MatterKind
    status: MatterStatus
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    conversation_count: int = 0
    document_count: int = 0


class MatterList(BaseModel):
    items: list[MatterOut]


class ConversationMove(BaseModel):
    """File a conversation under a matter, or null to unfile it."""

    matter_id: UUID | None


class HistoryHit(BaseModel):
    """One match in the user's own saved work. Never another user's."""

    kind: Literal["conversation", "message"]
    conversation_id: UUID
    message_id: UUID | None = None
    matter_id: UUID | None = None
    title: str | None = None
    snippet: str
    created_at: datetime


class HistorySearch(BaseModel):
    items: list[HistoryHit]


class MatterDetail(MatterOut):
    conversations: list["ConversationOut"] = []


class ShareCreated(BaseModel):
    """Shown ONCE: only a hash of the token is stored, so it cannot be shown again."""

    id: UUID
    token: str
    path: str = Field(description="Where the public page lives, e.g. /s/<token>")
    expires_at: datetime


class ShareLinkOut(BaseModel):
    id: UUID
    message_id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None = None


class ShareList(BaseModel):
    items: list[ShareLinkOut]


class SharedAnswer(BaseModel):
    """The PUBLIC view of one shared answer. Carries the checked citations, the
    data-as-of date, the CC BY credit and the not-legal-advice notice. Never the
    owner's identity, conversation, matter, judge or party names (judgment titles are
    never sent)."""

    question: str
    text: str
    citations: list[Citation]
    expires_at: datetime
    provenance: Provenance


class MatterDeleted(BaseModel):
    mode: Literal["unfile", "everything"]
    documents_deleted: int
    conversations_deleted: int


class AnswerProvenance(BaseModel):
    """Did the user's own material shape this stored answer? (Not the same thing as
    `Provenance` above, which is the data-as-of block.) Written when the answer is
    saved. Sharing is allowed only when both flags are false (PRD-v2 O14)."""

    shaped_by_upload: bool = False
    shaped_by_matter_fact: bool = False

    @property
    def shareable(self) -> bool:
        return not (self.shaped_by_upload or self.shaped_by_matter_fact)


class MessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    from_cache: bool = False
    citations: list[Citation] = []
    created_at: datetime
    shaped_by_upload: bool = False
    shaped_by_matter_fact: bool = False


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]
    provenance: Provenance | None = None


# ---------------------------------------------------------------- question helpers


class FollowupsOut(BaseModel):
    """Next-question suggestions for a saved answer. QUESTIONS ONLY: each is one short
    sentence ending in "?", with no citation marker. Running one is an ordinary new
    question through the full pipeline."""

    suggestions: list[str] = Field(default_factory=list, max_length=3)


class ImproveIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ImproveOut(BaseModel):
    """Editable text for the input box. Never contains a citation. `changed` is false
    when the helper could not improve the text (then `text` is the user's own)."""

    text: str
    changed: bool


# ---------------------------------------------------------------- search / cases / acts


class SearchHit(BaseModel):
    kind: CitationKind
    record_id: str
    title: str | None = None
    court: str | None = None
    year: int | None = None
    citation_string: str | None = None
    act_slug: str | None = None
    section: str | None = None
    snippet: str | None = None
    url: str | None = None


class SearchResponse(BaseModel):
    items: list[SearchHit]
    next_cursor: str | None = None
    provenance: Provenance


class CaseParagraph(BaseModel):
    anchor: str
    text: str


class CaseOut(BaseModel):
    """A judgment. No judges, no party names (unreliable fields)."""

    record_id: str
    title: str | None = None
    court: str | None = None
    decision_date: date | None = None
    case_number: str | None = None
    citation_string: str | None = Field(
        default=None, description="Shown as 'as recorded in the dataset'"
    )
    url: str | None = Field(default=None, description="pdf_url")
    paragraphs: list[CaseParagraph]
    provenance: Provenance


class SectionOut(BaseModel):
    act_slug: str
    act_name: str
    act_year: int | None = None
    section: str
    section_title: str | None = None
    text: str
    source_url: str | None = None
    in_force: bool | None = Field(
        default=None, description="Only meaningful when act_status_checked is true"
    )
    act_status_checked: bool = Field(
        description="False -> UI says 'in-force status not checked'"
    )
    provenance: Provenance


class StatsRow(BaseModel):
    court: str
    year: int
    outcome_label: str
    count: int


class CoverageItem(BaseModel):
    id: str
    label: str


class CoverageResponse(BaseModel):
    """What the dataset covers, read from the ONE coverage source (core/coverage.json).
    `status` is "placeholder" until data/coverage_report.py has measured the dataset.
    `sentence_approved` false means the wording is NEEDS-OWNER. Public, no login."""

    status: Literal["placeholder", "measured"]
    sentence: str
    sentence_approved: bool
    not_in_dataset_message: str
    courts: list[CoverageItem]
    instruments: list[CoverageItem]
    excluded: list[str]
    measured_at: str | None = None
    provenance: Provenance


class StatsResponse(BaseModel):
    """Descriptive counts only. Never predictions or win chances."""

    rows: list[StatsRow]
    live: bool
    provenance: Provenance


# ---------------------------------------------------------------- documents (uploads)

DocumentStatus = Literal["uploaded", "extracting", "indexing", "ready", "failed"]


class UploadCreate(BaseModel):
    filename: str
    mime_type: str
    size_bytes: int = Field(gt=0)


class UploadCreated(BaseModel):
    document_id: UUID
    upload_url: str
    expires_in_seconds: int


class DocumentOut(BaseModel):
    id: UUID
    filename: str
    status: DocumentStatus
    page_count: int | None = None
    fail_reason: str | None = None


# --------------------------------------------------------------- feedback, orgs


class FeedbackIn(BaseModel):
    message_id: UUID
    rating: Literal["up", "down"]
    reason: str | None = None
    comment: str | None = Field(default=None, max_length=2000)


class OrganisationCreate(BaseModel):
    name: str
    seats: int = Field(ge=3, description="Chambers minimum is 3 seats")


class OrganisationOut(BaseModel):
    id: UUID
    name: str
    seats: int


class MemberInvite(BaseModel):
    email: str


class MemberRemove(BaseModel):
    user_id: UUID


class Ok(BaseModel):
    ok: bool = True


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    fake_pipeline: bool = False
