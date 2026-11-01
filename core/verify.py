"""Step 9 of 11: the citation verifier. The part that must never be weakened.

Plain words: the model has written a draft with markers like [S1] after each point.
For every marker we run four checks. The first three are plain Python and ALWAYS run,
whether Jev is up, down or timing out:

  1. Retrieved for this question: the marker is one of S1..S8 handed to the model.
  2. Record exists: that passage's record_id is really in the corpus collection.
  3. Quotes match: every "quoted phrase" in the sentence is in that record's text,
     after normalising spaces and punctuation.
  4. Claim supported: Jev rates supports / partly / does not support.

A citation that fails is REMOVED. If that leaves a sentence with no surviving citation
the sentence is removed too (an uncited claim is worse than none). One note is added
saying an authority could not be verified, and a row per failure goes to
invented_citation_log with the reason. Survivors get status "verified" or "partly";
there is no "unverified" status. If Jev is down, check 4 did not run, so the best a
citation can be is "partly" (never a full tick without check 4).

The result is sealed with contracts.seal_answer(); show() accepts nothing else.
Citation strings are copied from the passage exactly as stored, never retyped.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict, dataclass

from adapters.decisions import DecisionUnavailable
from adapters.qdrant import VectorStoreUnavailable
from core.contracts import (
    Citation,
    CitationStatus,
    Deps,
    DraftAnswer,
    FailReason,
    Passage,
    RemovedCitation,
    VerifiedAnswer,
    register_seal_checker,
)
from core.settings import get_settings

# Wording belongs to docs/UX-COPY.md (note: an authority could not be verified).
NOTE_ONE = (
    "Note: one authority cited in this answer could not be verified and was removed."
)
NOTE_MANY = (
    "Note: {n} authorities cited in this answer could not be verified and were removed."
)

_MARKER = re.compile(r"[\[(]\s*(S\d+(?:\s*[,;]\s*S\d+)*)\s*[\])]", re.IGNORECASE)
# Words ending in a dot that do NOT end a sentence (a case name is one unit).
_ABBREVIATIONS = (
    "v",
    "vs",
    "No",
    "Nos",
    "Art",
    "Sec",
    "s",
    "R",
    "SCC",
    "Pvt",
    "Ltd",
    "Dr",
    "Mr",
    "Mrs",
    "Ms",
    "Smt",
    "Shri",
    "Ors",
    "Anr",
    "Co",
    "Inc",
    "St",
    "Hon",
    "Addl",
    "Dy",
)
_NOT_ABBREV = "".join(rf"(?<!\b{a}\.)" for a in _ABBREVIATIONS)
_BOUNDARY = re.compile(rf"(?<=[.!?]){_NOT_ABBREV}\s+(?=[A-Z\"“‘\[(])|\n+")
# Quoted spans: curly or straight double quotes, curly or word-bounded single quotes.
_QUOTE_SPAN = re.compile(r"“[^”]*”|\"[^\"]*\"|‘[^’]*’|(?<!\w)'[^']+'(?!\w)")

# Citation-shaped text that is NOT tied to a source marker (a case the model recalled).
_CITATION_SHAPES = (
    re.compile(r"\bAIR\s+\d{4}\s+(?:SC|[A-Z]{2,4})\s+\d+", re.IGNORECASE),
    re.compile(r"\(\d{4}\)\s*\d+\s*SCC\b", re.IGNORECASE),
    re.compile(r"\[\d{4}\]\s*(?:SUPP\.?\s*)?\d*\s*S\.?C\.?R\.?\s*\d+", re.IGNORECASE),
    re.compile(
        r"\b[A-Z][\w.&'\-]*(?:\s+[A-Z][\w.&'\-]*){0,5}\s+(?:v\.?|vs\.?|versus)\s+"
        r"[A-Z][\w.&'\-]*(?:\s+[A-Z][\w.&'\-]*){0,5}"
    ),
    re.compile(r"\bIn re\s+[A-Z][\w.&'\-]*(?:\s+[A-Z][\w.&'\-]*){0,5}"),
)


def normalise(text: str) -> str:
    """Tidy spaces and punctuation so a quote can be compared. Words are untouched.

    Quote marks and dashes are unified, all punctuation becomes a space, whitespace
    collapses. Case is kept: a changed word must still fail.
    """
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _norm_case_name(text: str) -> str:
    text = normalise(text).casefold()
    return re.sub(r"\b(?:vs|versus|v)\b", "v", text)


@dataclass
class _Fail:
    source_id: str
    record_id: str | None
    reason: FailReason


def _quote_spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _QUOTE_SPAN.finditer(text)]


def _quotes(sentence: str) -> list[str]:
    out = []
    for start, end in _quote_spans(sentence):
        q = sentence[start + 1 : end - 1].strip()
        if normalise(q):
            out.append(q)
    return out


def _unbalanced_quotes(sentence: str) -> bool:
    """A stray quote mark means we cannot tell what is quoted: fail closed."""
    return (
        sentence.count("\u201c") != sentence.count("\u201d")
        or sentence.count("\u2018") != sentence.count("\u2019")
        or sentence.count('"') % 2 == 1
    )


def _split(text: str) -> list[tuple[str, str]]:
    """Cut into (sentence, separator-after). Never cuts inside a quoted span."""
    spans = _quote_spans(text)
    out: list[tuple[str, str]] = []
    pos = 0
    for m in _BOUNDARY.finditer(text):
        if any(a < m.start() < b for a, b in spans):
            continue
        if m.start() > pos:
            out.append((text[pos : m.start()], m.group(0)))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], ""))
    return out


def _record_text(record: object) -> str | None:
    if record is None:
        return None
    if isinstance(record, str):
        return record
    text = getattr(record, "text", None)
    return text if isinstance(text, str) else None


async def _fetch_record(passage: Passage, deps: Deps) -> str | None:
    """Check 2. Uploads use the uploads collection with the owner's user_id."""
    if passage.kind == "upload":
        collection = deps.settings.QDRANT_UPLOADS_COLLECTION
        user_id = passage.user_id
    else:
        collection = deps.settings.CORPUS_COLLECTION
        user_id = None
    try:
        record = await deps.vectors.get_record(
            collection, passage.record_id, user_id=user_id
        )
    except (VectorStoreUnavailable, PermissionError):  # cannot confirm -> missing
        return None
    return _record_text(record)


async def _claim_support(sentence: str, passage: Passage, deps: Deps) -> CitationStatus:
    """Check 4. Jev down/timeout -> 'partly': checks 1-3 passed, 4 did not run."""
    clean = _MARKER.sub("", sentence).strip()
    try:
        support = await deps.decisions.claim_support(clean, passage)
    except (DecisionUnavailable, TimeoutError):  # no check 4 -> never a full tick
        return "partly"
    if support == "supports":
        return "verified"
    if support == "partly":
        return "partly"
    raise _ClaimNotSupported


class _ClaimNotSupported(Exception):
    pass


def _to_citation(
    passage: Passage, status: CitationStatus, quote: str | None
) -> Citation:
    return Citation(
        source_id=passage.source_id,
        record_id=passage.record_id,
        status=status,
        citation_string=passage.citation_string,  # exactly as stored
        pdf_url=passage.pdf_url,
        source_url=passage.source_url,
        title=passage.title,
        quote=quote,
        kind="act" if passage.kind == "act_section" else "judgment",
        anchor=passage.anchor,
        act_slug=passage.act_slug,
        section=passage.section,
    )


def _unretrieved_authority(sentence: str, passages: Sequence[Passage]) -> bool:
    """True if the sentence names a case/citation that is in none of the passages."""
    haystack = " ".join(
        [normalise(p.text) for p in passages]
        + [normalise(p.citation_string or "") for p in passages]
    )
    names = " ".join(_norm_case_name(p.title or "") for p in passages)
    body = _norm_case_name(haystack)
    plain = _MARKER.sub("", sentence)
    for shape in _CITATION_SHAPES:
        for m in shape.finditer(plain):
            found = m.group(0)
            if normalise(found) in haystack:
                continue
            if _norm_case_name(found) in names or _norm_case_name(found) in body:
                continue
            return True
    return False


async def verify(
    draft: DraftAnswer, passages: Sequence[Passage], deps: Deps
) -> VerifiedAnswer:
    """Run checks 1-4 on every citation, remove failures, log them, seal the answer."""
    by_label = {p.source_id: p for p in passages if p.source_id}
    sentences = _split(draft.text.strip())

    kept_sentences: list[tuple[str, str]] = []
    citations: dict[str, Citation] = {}
    removed: list[RemovedCitation] = []

    for sentence, sep in sentences:
        labels: list[str] = []
        for m in _MARKER.finditer(sentence):
            for label in re.split(r"\s*[,;]\s*", m.group(1)):
                labels.append(label.upper())
        quotes = _quotes(sentence)
        unbalanced = _unbalanced_quotes(sentence)

        # A real case named in the text but never retrieved this turn (check 1).
        if _unretrieved_authority(sentence, passages):
            removed.append(RemovedCitation("", None, "not_retrieved", sentence))
            continue

        failed: set[str] = set()
        passed: dict[str, Citation] = {}
        for label in dict.fromkeys(labels):
            passage = by_label.get(label)
            if passage is None:  # check 1
                removed.append(RemovedCitation(label, None, "not_retrieved", sentence))
                failed.add(label)
                continue
            record_text = await _fetch_record(passage, deps)  # check 2
            if record_text is None:
                removed.append(
                    RemovedCitation(
                        label, passage.record_id, "record_missing", sentence
                    )
                )
                failed.add(label)
                continue
            norm_record = normalise(record_text)
            padded = f" {norm_record} "
            bad_quote = unbalanced or any(
                f" {normalise(q)} " not in padded for q in quotes
            )
            if bad_quote:  # check 3
                removed.append(
                    RemovedCitation(
                        label, passage.record_id, "quote_not_found", sentence
                    )
                )
                failed.add(label)
                continue
            try:  # check 4
                status = await _claim_support(sentence, passage, deps)
            except _ClaimNotSupported:
                removed.append(
                    RemovedCitation(
                        label, passage.record_id, "claim_not_supported", sentence
                    )
                )
                failed.add(label)
                continue
            passed[label] = _to_citation(passage, status, quotes[0] if quotes else None)

        if labels and not passed:
            continue  # every citation failed: drop the now-unsupported sentence
        if failed:  # strip only the failed markers, keep the survivors
            sentence = _strip_markers(sentence, failed)
        kept_sentences.append((sentence, sep))
        for label, cit in passed.items():
            prev = citations.get(label)
            if prev is None or (prev.status == "verified" and cit.status == "partly"):
                citations[label] = cit

    text = "".join(s + sep for s, sep in kept_sentences).strip()
    if removed:
        n = len({(r.source_id, r.record_id, r.sentence) for r in removed})
        note = NOTE_ONE if n == 1 else NOTE_MANY.format(n=n)
        text = f"{text}\n\n{note}".strip()
        await deps.citation_log.write(draft.question, draft.model, tuple(removed))

    ordered = tuple(citations[k] for k in sorted(citations, key=lambda s: int(s[1:])))
    return seal_answer(text, ordered, removed)


# --- The seal -------------------------------------------------------------------------
# An HMAC over the answer's content, keyed by settings.SEAL_KEY (same on every process,
# so cached answers still pass). Only this module can make one; any later change to
# the text or citations breaks it. No key set = nothing can be sealed or accepted.
def _digest(
    answer_text: str, citations: Sequence[Citation], removed: Sequence[RemovedCitation]
) -> bytes:
    key = get_settings().SEAL_KEY.get_secret_value().encode()
    if not key:
        raise RuntimeError("SEAL_KEY is not set: refusing to seal or accept answers")
    body = json.dumps(
        [answer_text, [asdict(c) for c in citations], [asdict(r) for r in removed]],
        sort_keys=True,
        ensure_ascii=False,
    ).encode()
    return hmac.new(key, body, hashlib.sha256).digest()


def seal_answer(
    text: str, citations: Sequence[Citation], removed: Sequence[RemovedCitation] = ()
) -> VerifiedAnswer:
    """Make the sealed answer. Called ONLY from verify() in this file."""
    cits, rem = tuple(citations), tuple(removed)
    return VerifiedAnswer(text, cits, rem, _seal=_digest(text, cits, rem))


def _check_seal(answer: VerifiedAnswer) -> bool:
    try:
        expected = _digest(answer.text, answer.citations, answer.removed)
    except RuntimeError:
        return False
    return hmac.compare_digest(expected, answer._seal)


register_seal_checker(_check_seal)


def _strip_markers(sentence: str, failed: set[str]) -> str:
    def repl(m: re.Match[str]) -> str:
        labels = [x.upper() for x in re.split(r"\s*[,;]\s*", m.group(1))]
        keep = [x for x in labels if x not in failed]
        return f"[{', '.join(keep)}]" if keep else ""

    return re.sub(r"\s+", " ", _MARKER.sub(repl, sentence)).strip()


def assert_seal_key_configured() -> None:
    """Call at API startup: refuse to boot with no SEAL_KEY."""
    if not get_settings().SEAL_KEY.get_secret_value():
        raise RuntimeError("SEAL_KEY is not set: the verifier cannot seal answers")
