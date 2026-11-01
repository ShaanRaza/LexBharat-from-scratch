"""Request and response shapes. FastAPI turns these into the OpenAPI file that the
website's client is generated from (rule 3), so they are the public contract.

Note what is NOT here on purpose: judges, petitioner, respondent. Those fields failed the
audit and are never displayed (CLAUDE.md section 6).
"""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Provenance(BaseModel):
    """Added to every answer, stats page and Act page (docs/UX-COPY.md)."""

    data_as_of: str | None = None
    snapshot_version: str
    credit: str
    notice: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Page(BaseModel):
    """Cursor pagination: pass `next_cursor` back as `?cursor=` to get the next page."""

    next_cursor: str | None = None


# ---- me ---------------------------------------------------------------------
class MeOut(BaseModel):
    id: UUID
    email: str
    name: str | None = None
    role: str
    plan: str
    status: str
    answers_limit: int | None = Field(
        None, description="Monthly research answers for this plan. null = not set yet."
    )
    answers_used: int
    answers_left: int | None = None


class ConsentOut(BaseModel):
    id: UUID
    notice_version: str
    purpose: str
    given_at: datetime
    withdrawn_at: datetime | None = None


class ConsentList(BaseModel):
    items: list[ConsentOut]


class ConsentChange(BaseModel):
    notice_version: str = Field(min_length=1, max_length=64)
    purpose: str = Field(min_length=1, max_length=200)
    action: Literal["give", "withdraw"]


class DeleteAccountOut(BaseModel):
    status: Literal["deleted"] = "deleted"
    external_cleanup: Literal["queued"] = "queued"


# ---- conversations ----------------------------------------------------------
class ConversationCreate(BaseModel):
    module: Literal["research", "document"] = "research"
    document_id: UUID | None = None
    title: str | None = Field(None, max_length=200)


class ConversationOut(BaseModel):
    id: UUID
    module: str
    title: str | None = None
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationList(Page):
    items: list[ConversationOut]


class SourceOut(BaseModel):
    source_id: str
    record_id: str
    title: str | None = None
    citation: str | None = None
    citation_label: str | None = None
    url: str | None = None
    verified: bool
    support: str | None = None


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
    sources: list[SourceOut] = []


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]
    provenance: Provenance


class MessageCreate(BaseModel):
    # 4,000 characters is a placeholder cap, see decisions in the final report.
    content: str = Field(min_length=1, max_length=4000)


# ---- streaming events (documented here; sent as SSE, not JSON bodies) --------
class CitationOut(BaseModel):
    source_id: str
    record_id: str
    title: str | None = None
    citation: str | None = None
    citation_label: str | None = None
    url: str | None = None
    status: Literal["verified", "partly"]
    status_label: str


class CitationsEvent(BaseModel):
    """The ONE citations event, sent after verification (never before)."""

    citations: list[CitationOut]
    removed_count: int
    unverified_note: str | None = None
    outcome: Literal["answered", "not_found", "out_of_scope"]
    provenance: Provenance


class DoneEvent(BaseModel):
    message_id: UUID | None = None
    request_id: str


# ---- records ----------------------------------------------------------------
class Paragraph(BaseModel):
    anchor: str
    text: str


class CaseOut(BaseModel):
    record_id: str
    title: str | None = None
    court: str
    decision_date: date | None = None
    case_number: str | None = None
    citation: str | None = None
    citation_label: str | None = None
    disposition: str | None = None
    outcome_label: str | None = None
    pdf_url: str | None = None
    paragraphs: list[Paragraph]
    provenance: Provenance


class InForceStatus(BaseModel):
    checked: bool
    act_status: str | None = None
    in_force: bool | None = None
    label: str


class ActSectionOut(BaseModel):
    record_id: str
    act_name: str
    act_year: int | None = None
    section_number: str
    section_title: str | None = None
    text: str | None = None
    status: InForceStatus
    source_url: str | None = None
    provenance: Provenance


class StatRow(BaseModel):
    year: int
    outcome_label: str
    count: int


class StatsOut(BaseModel):
    court: str
    year: int | None = None
    rows: list[StatRow]
    total: int
    description: str
    provenance: Provenance


class SearchHitOut(BaseModel):
    record_id: str
    title: str | None = None
    snippet: str | None = None
    url: str | None = None
    court: str | None = None
    year: int | None = None


class SearchOut(BaseModel):
    items: list[SearchHitOut]
    provenance: Provenance


# ---- feedback / documents / billing ------------------------------------------
class FeedbackIn(BaseModel):
    message_id: UUID
    rating: Literal[1, -1] = Field(description="1 = thumbs up, -1 = thumbs down")
    reason: str | None = Field(None, max_length=200)
    comment: str | None = Field(None, max_length=2000)


class FeedbackOut(BaseModel):
    status: Literal["saved"] = "saved"


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str | None = Field(None, max_length=100)
    size_bytes: int | None = Field(None, ge=0)


class UploadOut(BaseModel):
    document_id: UUID
    upload_url: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    filename: str
    status: str
    fail_reason: str | None = None
    page_count: int | None = None
    expires_at: datetime | None = None


class WebhookOut(BaseModel):
    received: bool = True


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["ok"] = "ok"
