"""Step 10 - SHOW: turn a verified answer into what the user sees.

Text streams word by word; the checked citations arrive as ONE final event, after all
the text. A user must never see a citation appear and then vanish - so the streamed text
contains no markers at all, and every citation carries an `offset` saying where it
attaches. Each answer also carries the data-as-of date, the CC BY credit and the
not-legal-advice notice.

Refuses anything that did not come out of core.verify (rule: verify cannot be skipped).
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from adapters.qdrant import Record
from core import copy
from core.models import CitationView, FinalAnswer, VerifiedAnswer
from core.settings import Settings
from core.verify import is_sealed


class UnverifiedAnswerError(Exception):
    """show() was handed an answer that did not pass through the verifier."""


def _view(citation, record: Record) -> CitationView:
    label = copy.RECORD_FOUND
    if citation.status == "partly":
        label += " (supports only partly)"
    elif citation.status == "unchecked":
        label += " (support not checked)"
    in_force = ""
    if record.source_type == "act":  # only Acts have an in-force flag
        in_force = record.act_status or copy.IN_FORCE_NOT_CHECKED
    return CitationView(
        source_id=citation.source_id,
        record_id=citation.record_id,
        status=citation.status,
        label=label,
        title=record.title,
        url=record.pdf_url or record.source_url,
        offset=citation.offset,
        citation_string=record.citation,  # exactly as stored, never retyped
        citation_string_label=copy.CITATION_STRING_LABEL if record.citation else "",
        in_force_label=in_force,
    )


def show(
    verified: VerifiedAnswer,
    records: dict[str, Record],
    settings: Settings,
    *,
    safety: str = "normal",
) -> FinalAnswer:
    if not is_sealed(verified):
        raise UnverifiedAnswerError("answer did not come from the verifier")
    views = tuple(
        _view(c, records[c.record_id])
        for c in verified.citations
        if c.record_id in records
    )
    return FinalAnswer(
        text=verified.text,
        citations=views,
        note=copy.removed_note(len(verified.removed)) if verified.removed else "",
        opening=copy.PERSONAL_ADVICE_OPENING if safety == "personal_advice" else "",
        notice=copy.not_legal_advice(settings.PRODUCT_NAME),
        data_as_of=settings.DATA_AS_OF or settings.SNAPSHOT_VERSION,
        credit=copy.DATA_CREDIT,
    )


def stream_events(final: FinalAnswer) -> Iterator[dict]:
    """Event order is fixed: text words..., then exactly one 'citations' event, then done."""
    if final.opening:
        yield {"type": "text", "delta": final.opening + "\n\n"}
    for chunk in re.findall(r"\S+\s*", final.text):
        yield {"type": "text", "delta": chunk}
    yield {
        "type": "citations",
        "citations": [c.__dict__ for c in final.citations],
        "note": final.note,
        "notice": final.notice,
        "data_as_of": final.data_as_of,
        "credit": final.credit,
    }
    yield {"type": "done"}
