"""Step 5 - Search: top 50 from the law collection (and the user's uploads, if any)."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from adapters.qdrant import Hit, VectorStoreUnavailable
from adapters.voyage import VoyageUnavailable
from core.act_status import read_act_status
from core.contracts import (
    SEARCH_TOP_K,
    Decision,
    Deps,
    Passage,
    PassageKind,
    PipelineRequest,
    RewrittenQuery,
)
from core.dedupe import dedupe_passages
from core.hc_citation import case_reference, extract_neutral_citation
from core.settings import Settings
from core.uploads import search_user_documents

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    passages: tuple[Passage, ...]
    keyword_only: bool  # Voyage was down: label "keyword results only"


async def embed_query(text: str, deps: Deps) -> list[float] | None:
    """Embed the query. None = Voyage down (search degrades to keyword only)."""
    try:
        return await deps.embedder.embed(text, deps.settings.CORPUS_COLLECTION)
    except VoyageUnavailable:
        log.warning("voyage down; keyword-only search")
        return None


# An Act point's stored text opens "Act: <title> | India | <Central|State|Repealed> |
# <status>" (all 320 practice-fixture Act points do; the real collection is not checked,
# A105). Act points carry no char_start/char_end, so there is nothing to slice: the
# dataset's jurisdiction and status tail is matched and removed. Anchored to the LAST
# three "|" fields of an "Act:" line, so a title containing "|" cannot hide the tail.
_ACT_HEADER_TAIL = re.compile(r"^(Act:[^\n]*?)[ \t]*\|[^|\n]*\|[^|\n]*\|[^|\n]*$", re.M)


def strip_act_header_status(text: str) -> str:
    """Remove the dataset's "| India | Central | In Force" tail from an Act header line,
    so no unchecked status reaches the model (CLAUDE.md section 6). The status the
    model DOES see is the checked line from act_status_line()."""
    return _ACT_HEADER_TAIL.sub(lambda m: m.group(1), text)


def act_status_line(payload: dict, settings: Settings) -> str:
    """The one deterministic status line for an Act point, chosen by code from the
    payload (core/act_status.py), gated exactly as the website gates it (A181):
    repealed is always stated, in force only while SHOW_IN_FORCE is on, otherwise the
    not-checked line. A wording left empty in config adds no line."""
    reading = read_act_status(
        payload.get("act_id"),
        payload.get("title"),
        payload.get("act_status"),
        payload.get("is_repealed"),
        show_in_force=settings.SHOW_IN_FORCE,
    )
    return {
        "repealed": settings.ACT_STATUS_REPEALED,
        "in_force": settings.ACT_STATUS_IN_FORCE,
        "not_checked": settings.ACT_STATUS_NOT_CHECKED,
    }[reading.status]


def hit_to_passage(
    h: Hit, kind: PassageKind | None = None, settings: Settings | None = None
) -> Passage:
    p = h.payload
    text = h.text
    cs, ce = p.get("char_start"), p.get("char_end")
    if kind != "upload" and isinstance(cs, int) and isinstance(ce, int) and ce > cs:
        text = text[-(ce - cs) :]  # drop the "Case: ..." header, keep the body
    if kind is None:
        kind = "act_section" if "section_number" in p else "judgment"
    if kind == "act_section":
        text = strip_act_header_status(text)
        line = act_status_line(p, settings) if settings is not None else ""
        if line:
            text = f"{text.rstrip()}\n\n{line}"
    stored = (p.get("citation") or None) if kind == "judgment" else None
    neutral = reference = None
    if kind == "judgment" and not stored:
        # No stored citation (the dataset stores none for these). A stored string is never
        # touched. A neutral citation is read only from a chunk that STARTS the
        # judgment: a middle chunk has no header, and the body cites other cases.
        court, when = p.get("court"), p.get("decision_date")
        if cs == 0 and isinstance(ce, int) and ce > 0:  # body = header stripped
            neutral = extract_neutral_citation(text, court, when).citation
        if not neutral:
            reference = case_reference(p.get("case_number"), court, when)
    return Passage(
        record_id=h.record_id,
        text=text,
        kind=kind,
        score=h.score,
        citation_string=stored,
        neutral_citation=neutral,
        case_reference=reference,
        pdf_url=p.get("pdf_url") or None,
        source_url=p.get("source_url") or None,
        title=p.get("title") or None,
        act_status=p.get("act_status") or None,
        act_slug=p.get("act_id") or None,
        section=p.get("section_number") or None,
        page=p.get("page_start") if kind == "upload" else None,
        char_start=cs,
        char_end=ce,
        user_id=p.get("user_id"),
        case_id=(p.get("case_id") or None) if kind == "judgment" else None,
    )


def _must(decision: Decision) -> dict[str, str]:
    """Exact lookups (named section, case number) skip the merge: payload filter."""
    f, must = decision.filters, {}
    if f.section:
        must["section_number"] = str(f.section)
    if f.case_number:
        must["case_number"] = f.case_number
    return must


def _year_ok(h: Hit, decision: Decision) -> bool:
    f = decision.filters
    if not (f.year_from or f.year_to):
        return True
    try:
        y = int(h.payload.get("year"))
    except (TypeError, ValueError):
        return True
    return (not f.year_from or y >= f.year_from) and (not f.year_to or y <= f.year_to)


async def search(
    request: PipelineRequest,
    rq: RewrittenQuery,
    decision: Decision,
    vector: list[float] | None,
    deps: Deps,
) -> SearchResult:
    """Input: query, decision, query vector. Output: at most 50 passages, best first,
    with no two sharing a chunk id or a text (core/dedupe.py)."""
    must = _must(decision)
    law = deps.vectors.search(
        deps.settings.CORPUS_COLLECTION, vector, rq.query, must, SEARCH_TOP_K
    )
    jobs = [law]
    if request.document_ids and deps.settings.FEATURE_UPLOADS:
        jobs.append(
            search_user_documents(
                deps.vectors,
                request.user_id,
                vector,
                rq.query,
                request.document_ids,
                SEARCH_TOP_K,
            )
        )
    try:
        results = await asyncio.gather(*jobs)
    except VectorStoreUnavailable:
        log.error("vector store unavailable")
        raise
    passages = [
        hit_to_passage(h, settings=deps.settings)
        for h in results[0]
        if _year_ok(h, decision)
    ]
    if len(results) > 1:
        passages += [hit_to_passage(h, "upload") for h in results[1]]
    passages.sort(key=lambda p: -p.score)
    unique = dedupe_passages(passages)  # repeats out; corpus beats upload
    if len(unique) < len(passages):
        dropped = len(passages) - len(unique)
        log.info("search: dropped %d duplicate passage(s)", dropped)
    return SearchResult(tuple(unique[:SEARCH_TOP_K]), vector is None)
