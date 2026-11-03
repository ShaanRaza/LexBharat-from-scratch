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
invented_citation_log with the reason. Survivors get status "verified", "partly" or
"unchecked"; there is no "unverified" status. If Jev and Gemini are both down, check 4
did not run, so the citation is "unchecked" (shown as "Support not checked", no tick).
"partly" is kept only for a real "partly" rating.

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
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

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
# Quoted spans, in EVERY quotation form, so check 3 treats them all alike. Each form
# must open and close with ITS OWN marks: a mixed pair (an opening curly with a closing
# straight quote) is not a span, its marks are left over, and that fails closed.
#   straight "x"  curly “x”  low-9 „x“ or „x”  guillemets «x» or »x«  full-width ＂x＂
#   CJK 〝x〞 〝x〟  single: curly ‘x’  low-9 ‚x‘  ‹x› or ›x‹  「x」  『x』  and a
#   word-bounded straight 'x'.
_FULL_WIDTH_BRACKETS = str.maketrans("\uff3b\uff3d\uff08\uff09", "[]()")
_DQ = '"\u201c\u201d\u201e\u201f\u00ab\u00bb\uff02\u301d\u301e\u301f'
_QUOTE_SPAN = re.compile(
    r'"[^"]*"'
    r"|“[^”]*”"
    r"|„[^“”]*[“”]|‟[^”]*”"
    r"|«[^«»]*»|»[^«»]*«"
    r"|＂[^＂]*＂"
    r"|〝[^〝〞〟]*[〞〟]"
    r"|‘[^’]*’|‚[^‚‘’]*[‘’]"
    r"|‹[^‹›]*›|›[^‹›]*‹"
    r"|「[^「」]*」|『[^『』]*』"
    r"|(?<!\w)'[^']+'(?!\w)"
)
# A quotation mark left over after the matched spans are removed: we cannot tell what is
# quoted, so fail closed.
_STRAY_QUOTE = re.compile(rf"[{_DQ}‹›「」『』‚‛]")

# Citation-shaped text that is NOT tied to a source marker (a case the model recalled).
# These run on a DETECTION COPY of the sentence (see _detect_form): dots between single
# letters are gone (A.I.R. -> AIR), invisible characters are stripped, look-alike
# letters are folded to Latin and whitespace (line breaks included) is one space. The
# answer text itself is never changed by this.
_CITATION_SHAPES = (
    # AIR 1973 SC 1461 / AIR 1965 Guj. 23 / AIR 1940 Madras 29 / AIR1973SC1461: the
    # court part is any short word or the spelled-out form, so the many court
    # abbreviations used in AIR citations are all recognised.
    re.compile(
        r"\bAIR\s*\d{4}\s*(?:Supreme\s+Court|[A-Za-z]{2,10})\.?\s*\d+", re.IGNORECASE
    ),
    re.compile(r"\b\d{4}\s+AIR\s*(?:SC\s*)?\d+", re.IGNORECASE),  # 1973 AIR 1461
    re.compile(r"\bSCC\s*OnLine\b[\w\s]{0,12}\d+", re.IGNORECASE),
    # (1973) 4 SCC 225 / ( 1973 ) 4 SCC 225 / (1973)4SCC225
    re.compile(r"\(\s*\d{4}\s*\)\s*\d+\s*SCC(?![A-Za-z])", re.IGNORECASE),
    re.compile(
        r"\b\d{4}\s*\(\s*\d+\s*\)\s*SCC(?![A-Za-z])", re.IGNORECASE
    ),  # 1973 (4) SCC
    re.compile(
        r"\[\s*\d{4}\s*\]\s*(?:SUPP(?:L)?\.?\s*)?\d*\s*S\.?C\.?R\.?\s*\d+",
        re.IGNORECASE,
    ),
    re.compile(r"\bMANU\s*/\s*[A-Z]{2,4}\s*/\s*\d+\s*/\s*\d{4}", re.IGNORECASE),
    # (A case NAME "X v. Y" is not tested here: _unretrieved_authority checks it below
    # with the whole name, A117. This tuple is reporter citations and "In re".)
    re.compile(r"\bIn re\s+[A-Z][\w.&'\-]*(?:\s+[A-Z][\w.&'\-]*){0,5}"),
)
# "<word> v <word>" in any case, any spelling of v/vs/versus/V./Vs.: the anchor of a
# case name. (`versus` was only caught by the name shape that A117 replaced.)
_VERSUS_CORE = re.compile(r"(\S+)\s+(?:v|vs|versus)(?:\.\s*|\s+)(\S+)", re.IGNORECASE)
# Letters that look like Latin ones (Cyrillic, Greek, small capitals), folded for
# detection.
_CONFUSABLES = str.maketrans(
    {
        **{c: "a" for c in "а\u03b1\u1d00"},
        **{c: "e" for c in "е\u03b5\u1d07"},
        **{c: "o" for c in "о\u03bf\u1d0f"},
        **{c: "p" for c in "р\u03c1\u1d18"},
        **{c: "c" for c in "с\u1d04"},
        **{c: "x" for c in "х\u03c7"},
        **{c: "y" for c in "у\u03b3\u028f"},
        **{c: "i" for c in "і\u03b9\u026a"},
        **{c: "j" for c in "ј\u1d0a"},
        **{c: "s" for c in "ѕ\ua731"},
        **{c: "v" for c in "ѵ\u03bd\u1d20"},
        **{c: "h" for c in "һ\u029c"},
        **{c: "d" for c in "ԁ\u1d05"},
        **{c: "k" for c in "\u03ba\u1d0b"},
        **{c: "t" for c in "\u03c4\u1d1b"},
        **{c: "u" for c in "\u03c5\u1d1c"},
        **{c: "g" for c in "\u0261\u0262"},
        **{c: "r" for c in "\u0280"},
        **{c: "l" for c in "\u029f"},
        **{c: "m" for c in "\u1d0d"},
        **{c: "n" for c in "\u0274"},
        **{c: "b" for c in "\u0299"},
        **{c: "z" for c in "\u1d22"},
        **{c: "w" for c in "\u1d21"},
        # capitals
        **{c: "A" for c in "А\u0391"},
        **{c: "B" for c in "В\u0392"},
        **{c: "E" for c in "Е\u0395"},
        **{c: "K" for c in "К\u039a"},
        **{c: "M" for c in "М\u039c"},
        **{c: "H" for c in "Н\u0397"},
        **{c: "O" for c in "О\u039f"},
        **{c: "P" for c in "Р\u03a1"},
        **{c: "C" for c in "С"},
        **{c: "T" for c in "Т\u03a4"},
        **{c: "X" for c in "Х\u03a7"},
        **{c: "Y" for c in "\u03a5"},
        **{c: "I" for c in "І\u0399"},
        **{c: "S" for c in "Ѕ"},
        **{c: "Z" for c in "\u0396"},
        **{c: "N" for c in "\u039d"},
    }
)
_SINGLE_LETTER_DOTS = re.compile(r"\b(?:[A-Za-z]\.){2,}")


def _detect_form(text: str) -> str:
    """A copy of `text` for DETECTING recalled authorities, never shown to anyone:
    NFKC, invisible characters (category Cf) removed, look-alike letters folded to
    Latin, A.I.R. / S.C.C. / S.C. written without dots, whitespace (line breaks too)
    collapsed to one space."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Cf")
    text = text.translate(_CONFUSABLES)
    text = _SINGLE_LETTER_DOTS.sub(lambda m: m.group(0).replace(".", ""), text)
    return " ".join(text.split())


# A line break right next to v / vs / versus must not split a case name in two.
_BREAK_AFTER_VERSUS = re.compile(r"\b(v|vs|versus)(\.?)[ \t]*\n[ \t]*", re.IGNORECASE)
_BREAK_BEFORE_VERSUS = re.compile(r"[ \t]*\n[ \t]*(?=(?:v|vs|versus)\b)", re.IGNORECASE)


def _join_versus_breaks(text: str) -> str:
    text = _BREAK_AFTER_VERSUS.sub(lambda m: f"{m.group(1)}{m.group(2)} ", text)
    return _BREAK_BEFORE_VERSUS.sub(" ", text)


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
    """A stray or unrecognised quote mark (stray, backtick) means we cannot tell
    what is quoted: fail closed."""
    rest = _QUOTE_SPAN.sub(" ", sentence)
    return (
        "`" in sentence
        or "\u00b4" in sentence
        or bool(_STRAY_QUOTE.search(rest))
        or sentence.count("\u2018") != sentence.count("\u2019")
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
    """Check 4. Decider down/timeout -> 'unchecked': checks 1-3 passed, 4 did not."""
    clean = _MARKER.sub("", sentence).strip()
    try:
        support = await deps.decisions.claim_support(clean, passage)
    except (DecisionUnavailable, TimeoutError):  # no check 4 -> no tick at all
        return "unchecked"
    if support == "supports":
        return "verified"
    if support == "partly":
        return "partly"
    raise _ClaimNotSupported


class _ClaimNotSupported(Exception):
    pass


_STRENGTH = {"unchecked": 0, "partly": 1, "verified": 2}  # keep the weakest


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


def _squash(text: str) -> str:
    """Letters and digits only, so 'AIR1978SC597' equals 'AIR 1978 SC 597'."""
    return re.sub(r"\W", "", text).casefold()


# --- Case names (A117, rule f of A116) ----------------------------------------------
# A written case name is accepted as retrieved only if EVERY word of it appears, in
# order, inside ONE retrieved case name (a passage title, or a "... v ..." span in a
# passage's text), and at least one word is not generic. "Generic" = a word in at least
# 1% of case titles, read from core/generic_title_words.json, which is DERIVED from the
# titles (evals/title_rules.py --write-generic), never typed. Words match if equal, or
# alike letter by letter (5+ letters, 80%), or a known abbreviation pair. Replaces the
# old "one word either side of v" test, which rejected 61% of legitimate shortened
# names and accepted 3% to 7.5% of invented ones (A113, A115, A116).
_GENERIC_FILE = Path(__file__).with_name("generic_title_words.json")
_ABBREV_CANON = {
    "company": "co",
    "limited": "ltd",
    "private": "pvt",
    "corporation": "corpn",
}
# ("in" is not one: "the Court in Smith v. X" must not pull "Court in" into the name)
_NAME_JOINERS = {"&", "and", "of", "for"}
_REPORTERS = {"AIR", "SCC", "SCR", "SC", "ILR", "INSC", "MANU"}
# Discourse words that can open a sentence in front of a name ("In Smith v. X, ...").
_LEAD_WORDS = {"in", "see", "per", "also", "cf", "under", "following", "as"}
_NAME_SIDE = 7  # words kept either side of the v
_SPAN_SIDE = 8  # words kept either side of a v in a passage's text


@lru_cache(maxsize=1)
def _generic_words() -> frozenset[str]:
    """Generic title words. Fails closed: a missing or empty list raises, because with
    no list every word would count as distinctive and "State v. Union" would pass."""
    try:
        words = json.loads(_GENERIC_FILE.read_text(encoding="utf-8"))["words"]
    except (OSError, KeyError, ValueError) as e:
        raise RuntimeError(f"{_GENERIC_FILE.name} is missing or unreadable") from e
    if not words:
        raise RuntimeError(f"{_GENERIC_FILE.name} has no words")
    return frozenset(words)


def _name_like(raw: str, first_of_party: bool) -> bool:
    word = raw.strip(".,;:()[]\"'")
    if not word or word in _REPORTERS:
        return False
    if word[0].isupper():
        return True
    low = word.lower()
    return low in _NAME_JOINERS or (first_of_party and low == "the")


def _is_number(raw: str) -> bool:
    return normalise(raw).isdigit()


def _case_names(plain: str) -> list[list[str]]:
    """Every written case name in `plain`, as normalised words with "v" between the
    parties. The two words next to the v are ALWAYS kept (as before), so a name in
    lower case or odd spacing is still checked; more are added while they still look
    like part of a party name, and stop at punctuation that ends the clause."""
    out = []
    for m in _VERSUS_CORE.finditer(plain):
        left = plain[: m.end(1)].split()
        right = plain[m.start(2) :].split()
        # A side that is bare punctuation ("State v. & Ors.") is looked past, to the
        # next word-like token, instead of abandoning the name (A121).
        while left and not normalise(left[-1]):
            left.pop()
        while right and not normalise(right[0]):
            right.pop(0)
        if not left or not right:
            continue  # nothing on one side to check
        # "Article 14 v. Article 19": a number on EACH side: not a case. A number
        # on one side ("Zorblax v. 1 Vedanta Limited") is a numbered party: checked.
        if any(map(_is_number, left[-2:])) and any(map(_is_number, right[:2])):
            continue
        keep_left, keep_right = [left[-1]], [right[0]]
        for tok in reversed(left[:-1][-_NAME_SIDE:]):
            if tok[-1] in ",;:)]" or not _name_like(tok, False):
                break
            keep_left.append(tok)
        if keep_right[0][-1] not in ",;:)]":
            for tok in right[1:][:_NAME_SIDE]:
                if not _name_like(tok, False):
                    break
                keep_right.append(tok)
                if tok[-1] in ",;:)]":
                    break
        keep_left.reverse()
        while len(keep_left) > 1 and (
            keep_left[0].lower() in _LEAD_WORDS
            or keep_left[0].lower() in _NAME_JOINERS - {"&"}
        ):
            keep_left.pop(0)
        while len(keep_right) > 1 and keep_right[-1].strip(".,;:()[]").lower() in (
            _NAME_JOINERS | {"the"}
        ):
            keep_right.pop()
        words = _norm_case_name(" ".join(keep_left + ["v"] + keep_right)).split()
        # "M/s" says nothing about WHICH case, but never strip a left party down to
        # nothing: that would leave no name to check (fail open).
        v_at = words.index("v") if "v" in words else 0
        if words[:2] == ["m", "s"] and v_at > 2:
            words = words[2:]
        elif words[:1] == ["messrs"] and v_at > 1:
            words = words[1:]
        if words and words[0] != "v" and words[-1] != "v":
            out.append(words)
    return out


def _same_word(a: str, b: str) -> bool:
    a, b = _ABBREV_CANON.get(a, a), _ABBREV_CANON.get(b, b)
    if a == b:
        return True
    return min(len(a), len(b)) >= 5 and SequenceMatcher(None, a, b).ratio() >= 0.8


def _in_order(name: Sequence[str], cand: Sequence[str]) -> bool:
    """Every word of `name` is matched, in order, by a word of `cand`."""
    prev = [0] * (len(cand) + 1)
    for w in name:
        cur = [0]
        for j, c in enumerate(cand):
            cur.append(prev[j] + 1 if _same_word(w, c) else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1] == len(name)


def _retrieved_names(passages: Sequence[Passage]) -> list[list[str]]:
    out = []
    for p in passages:
        if p.title:
            out.append(_norm_case_name(p.title).split())
        toks = _norm_case_name(p.text).split()
        for i, t in enumerate(toks):
            if t == "v" and 0 < i < len(toks) - 1:
                out.append(toks[max(0, i - _SPAN_SIDE) : i + _SPAN_SIDE + 1])
    return out


def _has_run(name: Sequence[str], cand: Sequence[str]) -> bool:
    n = len(name)
    return any(list(cand[i : i + n]) == list(name) for i in range(len(cand) - n + 1))


def _name_was_retrieved(
    name: Sequence[str], candidates: Sequence[Sequence[str]]
) -> bool:
    generic = _generic_words() | {"v"}
    if all(w in generic for w in name):
        # No distinctive word: "State v. Union" names no case, and an ordered match
        # would accept it from any longer name. Only an EXACT run can verify it (a name
        # typed in lower case shrinks to the two words beside the v, which may both be
        # generic: "pradesh v sri").
        return any(_has_run(name, c) for c in candidates)
    return any(_in_order(name, c) for c in candidates)


def _unretrieved_authority(sentence: str, passages: Sequence[Passage]) -> bool:
    """True if the sentence names a case/citation that is in none of the passages."""
    haystack = " ".join(
        [normalise(p.text) for p in passages]
        + [normalise(p.citation_string or "") for p in passages]
    )
    squashed = _squash(
        " ".join(p.text + " " + (p.citation_string or "") for p in passages)
    )
    names = " ".join(_norm_case_name(p.title or "") for p in passages)
    body = _norm_case_name(haystack)
    plain = _detect_form(_MARKER.sub("", sentence))
    for shape in _CITATION_SHAPES:
        for m in shape.finditer(plain):
            found = m.group(0)
            if normalise(found) in haystack:
                continue
            if _squash(found) and _squash(found) in squashed:
                continue
            if _norm_case_name(found) in names or _norm_case_name(found) in body:
                continue
            return True
    # A case name in ANY case / spelling of v: every word of it must appear, in order,
    # inside one retrieved case name (and one word must not be generic), or it was
    # recalled. (A117; the old test compared only the word either side of the v.)
    names_found = _case_names(plain)
    if names_found:
        candidates = _retrieved_names(passages)
        for name in names_found:
            if not _name_was_retrieved(name, candidates):
                return True
    return False


async def verify(
    draft: DraftAnswer, passages: Sequence[Passage], deps: Deps
) -> VerifiedAnswer:
    """Run checks 1-4 on every citation, remove failures, log them, seal the answer."""
    by_label = {p.source_id: p for p in passages if p.source_id}
    draft_text = _join_versus_breaks(draft.text.translate(_FULL_WIDTH_BRACKETS)).strip()
    sentences = _split(draft_text)

    kept_sentences: list[tuple[str, str]] = []
    citations: dict[str, Citation] = {}
    removed: list[RemovedCitation] = []

    for sentence, sep in sentences:
        labels: list[str] = []
        for m in _MARKER.finditer(sentence):
            for label in re.split(r"\s*[,;]\s*", m.group(1)):
                labels.append(label.upper())
        if labels and not re.sub(r"[\W_]", "", _MARKER.sub("", sentence)):
            continue  # a bare "[S1]" left over from a removed sentence: drop it
        quotes = _quotes(sentence)
        unbalanced = _unbalanced_quotes(sentence)

        # Quoted words anywhere in the answer, cited or not, must be in a passage.
        if not labels and (quotes or unbalanced):
            pool = f" {' '.join(normalise(p.text) for p in passages)} "
            if unbalanced or any(f" {normalise(q)} " not in pool for q in quotes):
                removed.append(RemovedCitation("", None, "quote_not_found", sentence))
                continue

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
            if prev is None or _STRENGTH[cit.status] < _STRENGTH[prev.status]:
                citations[label] = cit

    # A case name split across two sentences (a line break or a stray dot inside it)
    # hides from the per-sentence check: look at neighbouring pairs too and fail closed.
    safe: list[tuple[str, str]] = []
    skip_next = False
    for i, (sent, sep) in enumerate(kept_sentences):
        if skip_next:
            skip_next = False
            continue
        if i + 1 < len(kept_sentences):
            nxt, nsep = kept_sentences[i + 1]
            pair = f"{sent}{sep}{nxt}"
            if _unretrieved_authority(pair, passages):
                removed.append(RemovedCitation("", None, "not_retrieved", pair))
                skip_next = True
                continue
        safe.append((sent, sep))
    kept_sentences = safe

    text = "".join(s + sep for s, sep in kept_sentences).strip()
    if removed:
        n = len({(r.source_id, r.record_id, r.sentence) for r in removed})
        note = NOTE_ONE if n == 1 else NOTE_MANY.format(n=n)
        text = f"{text}\n\n{note}".strip()
        await deps.citation_log.write(draft.question, draft.model, tuple(removed))

    # Only citations whose marker is carried by a sentence that survived.
    shown = {
        lab.upper()
        for m in _MARKER.finditer(text)
        for lab in re.split(r"\s*[,;]\s*", m.group(1))
    }
    citations = {k: v for k, v in citations.items() if k in shown}
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
