"""Step 9 - VERIFY: the citation verifier. The part that must never be weakened.

Plain words: the model writes an answer with markers like [S2] after each point. For
every marker we ask four questions. The citation survives only if ALL four pass.

  1. Retrieved this turn?   Was S2 really one of the passages we gave the model?  (free)
  2. Record exists?         Does that passage's record_id exist in the corpus?     (free)
  3. Quotes match?          Are words in "quotation marks" really in that record?  (free)
  4. Claim supported?       Does the passage support the sentence? (Jev / fallback)

Checks 1-3 are plain Python and ALWAYS run - Jev up or down. A failed citation is
removed from the text and returned in `removed` with its reason (the caller logs it to
invented_citation_log). A citation is NEVER shown as verified unless it passed.

"Cannot be skipped": `verify_answer` is the only code that can create a *sealed*
VerifiedAnswer, and `show()` refuses unsealed ones. There is no `skip` flag anywhere.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import secrets
import unicodedata
from dataclasses import dataclass

from adapters.jev import DecisionAdapter, DecisionUnavailable
from adapters.qdrant import VectorStore
from core.constants import (
    CLAIM_NOT_SUPPORTED,
    NOT_RETRIEVED,
    QUOTE_NOT_FOUND,
    RECORD_MISSING,
)
from core.models import CheckedCitation, RemovedCitation, Source, VerifiedAnswer

_SEAL_KEY = secrets.token_bytes(32)  # lives only in this process and this module

# [S1]  [S1][S2]  [S1, S2]  - any S-number, so a made-up [S9] is caught by check 1.
MARKER = re.compile(r"\[\s*(S\d+(?:\s*,\s*S\d+)*)\s*\]")
_QUOTE = re.compile(r'"([^"]+)"|“([^”]+)”')
_ELLIPSIS = re.compile(r"\.{3}|…")
# Words that end in a full stop without ending a sentence ("State v. Union").
_ABBREVIATIONS = {
    "v", "vs", "no", "nos", "sec", "art", "s", "ss", "dr", "mr", "mrs", "ltd", "co",
    "anr", "ors", "etc", "viz", "cl", "ch", "r", "w", "p", "pvt",
}  # fmt: skip


# --------------------------------------------------------------------------
# Parsing the draft
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedCitation:
    source_id: str
    offset: int  # position in the clean text where the marker used to be
    sentence: str  # the sentence the marker is attached to


def sentence_start(text: str) -> int:
    """Index where the last sentence in `text` begins (heuristic, abbreviation-aware)."""
    start = 0
    for m in re.finditer(r"[.!?]\s+|\n+", text):
        if m.group(0)[0] == ".":
            words = re.findall(r"[A-Za-z]+", text[: m.start() + 1])
            if words and words[-1].casefold() in _ABBREVIATIONS:
                continue
        start = m.end()
    return start


def parse_draft(raw: str) -> tuple[str, list[ParsedCitation]]:
    """Strip all [S#] markers; return the clean text and where each marker sat."""
    pieces: list[str] = []
    pending: list[tuple[str, int]] = []  # (source_id, offset)
    clean_len = 0
    pos = 0
    for m in MARKER.finditer(raw):
        segment = raw[pos : m.start()]
        segment = segment.removesuffix(" ")  # "claim [S1]." -> "claim."
        pieces.append(segment)
        clean_len += len(segment)
        for sid in dict.fromkeys(s.strip() for s in m.group(1).split(",")):
            pending.append((sid, clean_len))
        pos = m.end()
    pieces.append(raw[pos:])
    clean = "".join(pieces)

    parsed = []
    for sid, offset in pending:
        before = clean[:offset].rstrip()
        if before and before[-1] in ".!?":  # marker came after the full stop
            before = before[:-1]
        start = sentence_start(before)
        parsed.append(ParsedCitation(sid, offset, before[start:].strip()))
    return clean, parsed


# --------------------------------------------------------------------------
# Check 3: quotes
# --------------------------------------------------------------------------


def normalise(text: str) -> str:
    """Lower-case, fold look-alike characters, turn every space/punctuation run into one
    space. 'The  Court's "bail"' and 'the court s bail' compare equal."""
    text = unicodedata.normalize("NFKC", text).casefold()
    out = []
    for ch in text:
        if ch.isspace() or ch == "_" or unicodedata.category(ch)[0] in "PS":
            out.append(" ")
        else:
            out.append(ch)
    return " ".join("".join(out).split())


def extract_quotes(sentence: str) -> list[str]:
    """Every run of words inside double quotes (straight or curly)."""
    return [(a or b).strip() for a, b in _QUOTE.findall(sentence) if (a or b).strip()]


def quote_in_record(quote: str, record_text: str) -> bool:
    """True if every piece of the quote appears in the record as whole words, in order.

    A quote with "..." or an ellipsis is split into pieces; each piece must appear.
    """
    haystack = f" {normalise(record_text)} "
    for fragment in _ELLIPSIS.split(quote):
        needle = normalise(fragment)
        if needle and f" {needle} " not in haystack:
            return False
    return True


def quotes_match(sentence: str, record_text: str) -> bool:
    return all(quote_in_record(q, record_text) for q in extract_quotes(sentence))


# --------------------------------------------------------------------------
# The verifier
# --------------------------------------------------------------------------


async def verify_answer(
    draft_text: str,
    sources: tuple[Source, ...],
    store: VectorStore,
    decisions: DecisionAdapter,
    *,
    is_upload_chat: bool = False,
) -> VerifiedAnswer:
    clean, parsed = parse_draft(draft_text)
    by_id = {s.source_id: s for s in sources}

    removed: list[RemovedCitation] = []
    survivors: list[tuple[ParsedCitation, Source]] = []

    # Checks 1-3: free, always run, no outside service except the record lookup.
    for cite in parsed:
        source = by_id.get(cite.source_id)
        if source is None:  # check 1
            removed.append(
                RemovedCitation(cite.source_id, NOT_RETRIEVED, cite.sentence)
            )
            continue
        record = await store.get_record(source.record_id)
        if record is None:  # check 2
            removed.append(
                RemovedCitation(cite.source_id, RECORD_MISSING, cite.sentence)
            )
            continue
        if not quotes_match(cite.sentence, record.text):  # check 3
            removed.append(
                RemovedCitation(cite.source_id, QUOTE_NOT_FOUND, cite.sentence)
            )
            continue
        survivors.append((cite, source))

    # Check 4: claim supported. Jev, or the Gemini fallback, or "unchecked" if both down.
    async def rate(cite: ParsedCitation, source: Source):
        try:
            return await decisions.claim_support(
                cite.sentence, source.text, contains_upload_text=is_upload_chat
            )
        except DecisionUnavailable:
            return None

    ratings = await asyncio.gather(*(rate(c, s) for c, s in survivors))

    kept: list[CheckedCitation] = []
    for (cite, source), rating in zip(survivors, ratings, strict=True):
        if rating is None:  # passed 1-3 but check 4 could not run: never "verified"
            status, conf, who = "unchecked", 0.0, ""
        elif rating.choice == "does_not_support":
            removed.append(
                RemovedCitation(cite.source_id, CLAIM_NOT_SUPPORTED, cite.sentence)
            )
            continue
        elif rating.choice == "partly":
            status, conf, who = "partly", rating.confidence, rating.source
        else:
            status, conf, who = "verified", rating.confidence, rating.source
        kept.append(
            CheckedCitation(
                source_id=cite.source_id,
                record_id=source.record_id,
                sentence=cite.sentence,
                offset=cite.offset,
                status=status,
                support_confidence=conf,
                support_source=who,
            )
        )

    kept_sentences = {c.sentence for c in kept}
    unverified = tuple(
        dict.fromkeys(r.sentence for r in removed if r.sentence not in kept_sentences)
    )
    kept_tuple = tuple(sorted(kept, key=lambda c: c.offset))
    removed_tuple = tuple(removed)
    return VerifiedAnswer(
        text=clean,
        citations=kept_tuple,
        removed=removed_tuple,
        unverified_sentences=unverified,
        total_cited=len(parsed),
        _seal=_seal_for(clean, kept_tuple, removed_tuple, unverified, len(parsed)),
    )


def _seal_for(text, citations, removed, unverified, total_cited) -> str:
    """Keyed hash of the answer's content. Change any field and the seal no longer fits."""
    content = repr((text, citations, removed, unverified, total_cited))
    return hmac.new(_SEAL_KEY, content.encode(), hashlib.sha256).hexdigest()


def is_sealed(answer: VerifiedAnswer) -> bool:
    """True only for answers made by verify_answer and not changed since (used by show())."""
    expected = _seal_for(
        answer.text,
        answer.citations,
        answer.removed,
        answer.unverified_sentences,
        answer.total_cited,
    )
    return hmac.compare_digest(expected, answer._seal)
