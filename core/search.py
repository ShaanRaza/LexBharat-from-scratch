"""Step 5 - Search: top 50 from the law collection (and the user's uploads, if any)."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from adapters.qdrant import DenseGroup, Hit, QueryVectors, VectorStoreUnavailable
from adapters.voyage import VoyageUnavailable
from core import model_plan
from core.act_ids import plain_section, resolve_act
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


# The key an exact-section lookup filters on: the section a chunk's OWN heading
# names (research_v3 carries it on every chunk, indexed). `section_number` is a
# label the chunker wrote and not an address: an amended section is appended into
# the chunk of the section before and carries that one's number (docs/DATASET.md,
# "The section_number trap").
SECTION_KEY = "heading_section"


@dataclass(frozen=True)
class SectionNotHeld:
    """The user named a section of an Act we hold, and no chunk of that Act is
    headed by that section."""

    act_ids: tuple[str, ...]
    section: str


@dataclass(frozen=True)
class SearchResult:
    passages: tuple[Passage, ...]
    keyword_only: bool  # Voyage was down: label "keyword results only"
    # which layer of the filter ladder served the search (see _law_hits):
    # "act+section", "act", "section signal", "case number", "unfiltered" or
    # "section not held"
    scope: str = "unfiltered"
    # set only when scope == "section not held": no passages, and the Act's other
    # text is NOT served in its place
    not_held: SectionNotHeld | None = None


async def embed_query(text: str, deps: Deps) -> list[float] | QueryVectors | None:
    """Embed the query. None = Voyage down (search degrades to keyword only).

    A single-model collection is embedded once, as before. A collection embedded per
    court (A128) is embedded once per MODEL, concurrently, and returned as one dense
    group per model, each to be searched only among the courts that model built. Any
    model failing to answer counts as Voyage down: a half-matched search would be
    silently uneven."""
    collection = deps.settings.CORPUS_COLLECTION
    plan = model_plan.plan_for(deps.settings, collection)
    try:
        if plan is None:
            return await deps.embedder.embed(text, collection, "query")
        results = await asyncio.gather(
            *(
                deps.embedder.embed(text, collection, "query", court_code=g.embed_code)
                for g in plan
            ),
            return_exceptions=True,
        )
    except VoyageUnavailable:
        log.warning("voyage down; keyword-only search")
        return None
    for r in results:
        if isinstance(r, VoyageUnavailable):
            log.warning("voyage down; keyword-only search")
            return None
        if isinstance(r, BaseException):
            raise r  # an unregistered model or a bug is not an outage
    return QueryVectors(
        tuple(DenseGroup(v, g.codes, g.no_court) for g, v in zip(plan, results))
    )


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
        # No stored citation (the dataset has none here). A stored string is never
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


def _year_ok(h: Hit, decision: Decision) -> bool:
    """The year filter dates JUDGMENTS. An Act's own `year` is the year it was enacted,
    so it never excludes an Act section ("judgments after 2015 on section 138 of the
    Negotiable Instruments Act" must still bring section 138, enacted 1881)."""
    f = decision.filters
    if not (f.year_from or f.year_to):
        return True
    if "section_number" in h.payload:  # an Act section, not a judgment
        return True
    try:
        y = int(h.payload.get("year"))
    except (TypeError, ValueError):
        return True
    return (not f.year_from or y >= f.year_from) and (not f.year_to or y <= f.year_to)


def _merge(first: list[Hit], second: list[Hit], limit: int) -> list[Hit]:
    """`first` all kept, then `second` up to the limit; a record in both counts once."""
    out: dict[str, Hit] = {h.record_id: h for h in first}
    for h in second:
        if h.record_id not in out and len(out) < limit:
            out[h.record_id] = h
    return list(out.values())[:limit]


def _is_section(h: Hit, section: str) -> bool:
    """A chunk is section N's text if its own heading names N. A chunk with no
    heading at all (3,865 of the 72,185 plain-numbered Act chunks of research_v3:
    the chunker left no `Section N:` line) has no heading to differ, so its label
    stands. A chunk headed by ANOTHER section is dropped, whatever its label says."""
    heading = str(h.payload.get(SECTION_KEY) or "").upper()
    if heading:
        return heading == section
    return str(h.payload.get("section_number") or "").upper() == section


async def _section_hits(run, section: str, must: dict, limit: int) -> list[Hit]:
    """Chunks that ARE section `section`: by heading, plus labelled-and-headless
    chunks (see `_is_section`); both lookups are exact payload filters."""
    by_heading, by_label = await asyncio.gather(
        run({**must, SECTION_KEY: section}, limit),
        run({**must, "section_number": section}, limit),
    )
    kept: dict[str, Hit] = {}
    for h in by_heading + by_label:
        if _is_section(h, section):
            kept.setdefault(h.record_id, h)
    return list(kept.values())[:limit]


async def _law_hits(
    decision: Decision, vector, rq: RewrittenQuery, deps: Deps
) -> tuple[list[Hit], str, SectionNotHeld | None]:
    """The law-collection search, with the exact-lookup filters LAYERED so that no
    filter the search could not scope can empty it (DECISIONS A144).

    1. The decider named an Act that resolves to stored Act id(s) AND a plain
       section: a hard filter on (act_id, heading_section), the section a chunk's
       own heading names, plus a chunk with no heading whose label is that section.
       A section is only read inside its own Act. If no chunk of the Act is that
       section, the result is the typed "section not held" (no passages): the Act's
       other sections are NOT served in its place, because text of a different
       section under a question about this one reads as an answer.
    2. The "section" is not a plain number (Order VII Rule 11): the Act alone, ranked
       as usual. Only when a section was NAMED; an Act mentioned with no section
       never scopes the search (that would drop the case law about it).
    3. The Act does not resolve (not stored, or no name): the section number is a
       RANKING SIGNAL, not a filter. The ordinary search runs unfiltered and, if
       there is a plain section, a few slots are reserved for the best chunks headed
       by that number in any Act, so the right section can still be found and
       nothing is excluded.
    4. A case number is a hard filter only while it finds something; otherwise the
       ordinary search runs.
    A year or an Act's name never filters here: only (act_id, section_number),
    act_id (when a section was named) and case_number do. act_id is a payload index
    in the served collection (before it was, the Act-only layer took 6 to 10 seconds
    a query against the adapter's 5 second timeout and was dropped; indexed it takes
    about 0.01 seconds)."""
    f = decision.filters
    collection = deps.settings.CORPUS_COLLECTION
    section = plain_section(f.section)
    act_ids = resolve_act(f.act)
    case = {"case_number": f.case_number} if f.case_number else {}

    async def run(must: dict, limit: int = SEARCH_TOP_K) -> list[Hit]:
        return await deps.vectors.search(collection, vector, rq.query, must, limit)

    if f.section and act_ids:
        if section:
            # no case number here: an Act's chunks carry none, so it could only
            # empty the lookup
            hits = await _section_hits(
                run, section, {"act_id": list(act_ids)}, SEARCH_TOP_K
            )
            if hits:
                return hits, "act+section", None
            return [], "section not held", SectionNotHeld(tuple(act_ids), section)
        hits = await run({"act_id": list(act_ids)})
        if hits:
            return hits, "act", None
    elif case:
        hits = await run(case)
        if hits:
            return hits, "case number", None
    if section:
        reserved = max(1, SEARCH_TOP_K // 5)  # a fifth of the slots, not all
        general, by_section = await asyncio.gather(
            run({}), _section_hits(run, section, {}, reserved)
        )
        if by_section:
            return _merge(by_section, general, SEARCH_TOP_K), "section signal", None
        return general, "unfiltered", None
    return await run({}), "unfiltered", None


async def search(
    request: PipelineRequest,
    rq: RewrittenQuery,
    decision: Decision,
    vector: list[float] | QueryVectors | None,
    deps: Deps,
) -> SearchResult:
    """Input: query, decision, query vector. Output: at most 50 passages, best first,
    with no two sharing a chunk id or a text (core/dedupe.py)."""
    law = _law_hits(decision, vector, rq, deps)
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
    law_hits, scope, not_held = results[0]
    passages = [
        hit_to_passage(h, settings=deps.settings)
        for h in law_hits
        if _year_ok(h, decision)
    ]
    if len(results) > 1:
        passages += [hit_to_passage(h, "upload") for h in results[1]]
    passages.sort(key=lambda p: -p.score)
    unique = dedupe_passages(passages)  # repeats out; corpus beats upload
    if len(unique) < len(passages):
        dropped = len(passages) - len(unique)
        log.info("search: dropped %d duplicate passage(s)", dropped)
    return SearchResult(tuple(unique[:SEARCH_TOP_K]), vector is None, scope, not_held)
