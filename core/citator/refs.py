"""Citator Phase 1 (SC only): find citation-shaped references in judgment text.

Plain words: a judgment cites earlier cases in a few printed styles. The stored citation field of a
SC case has exactly ONE style, SCR (`[1979] 3 S.C.R. 453`, 100% of 35,688 served cases,
measured 4 Nov 2026), so only SCR references and neutral citations (`2018 INSC 329`, which is the record
id `2018_INSC_329`) can be matched to a stored record directly. AIR, SCC and the rest are found and
counted here but are NOT resolved by this module.

The text is OCR of the printed law reports, so the patterns tolerate bracket swaps (`(2010]`), `l` for `1`,
glued tokens (`2SCC`, `6Suppl.`) and a space inside `S.C.R.`. A reference is only ever a *candidate*:
this module never says a reference is a real case, only that its shape matches.

Pipeline: none of the 11 steps. This is offline data work. It touches no verifier check.
"""

# ruff: noqa: E501  (prose docstring and OCR-pattern comments)
from __future__ import annotations

import re
from dataclasses import dataclass

# --- SCR -------------------------------------------------------------------------------------------

_YEAR = r"(?:18|19|20)\d\d"
_DIG = r"[\dlI]{1,3}"  # OCR reads the digit 1 as l or I
_SUPP = r"SUPP(?:L(?:EMENT)?)?\.?"
_ADDL = r"\(?\s*ADDL\.?\s*\)?"

SCR_RE = re.compile(
    rf"""
    [\[\(]?\s*(?P<year>{_YEAR})\s*[\]\)]?        # [1979]  (1979)  (1979]
    \s*(?:\(\s*(?P<pvol>{_DIG})\s*\)\s*)?        # 2003 (6) Suppl. SCR 1235
    (?P<mid>(?:\s*(?:{_SUPP}|{_ADDL}|{_DIG}))*)  # volume / Supp. / Addl. in any order
    \s*S\s?\.?\s?C\s?\.?\s?R\s?\.?               # S.C.R.  SCR
    \s*[,:]?\s*(?P<page>\d{{1,4}})(?!\d)         # first page
    """,
    re.I | re.X,
)

_MID_TOKEN = re.compile(rf"({_SUPP})|({_ADDL})|({_DIG})", re.I)


@dataclass(frozen=True)
class Ref:
    kind: str  # scr | neutral | scc | air | scc_online | other_reporter
    raw: str
    start: int  # offset of the match in the text searched
    end: int
    key: tuple  # normalised identity; its shape depends on `kind`
    note: str = ""  # e.g. "air_sc", "air_hc"


def _num(tok: str) -> int | None:
    t = tok.translate(str.maketrans({"l": "1", "I": "1", "|": "1"}))
    return int(t) if t.isdigit() else None


def scr_key(year: int, supp: bool, vol: int | None, addl: bool, page: int) -> tuple:
    return ("scr", year, supp, vol, addl, page)


def parse_scr(m: re.Match[str]) -> tuple | None:
    year = int(m["year"])
    mid = m["mid"] or ""
    supp = addl = False
    vol: int | None = _num(m["pvol"]) if m["pvol"] else None
    for t in _MID_TOKEN.finditer(mid):
        if t.group(1):
            supp = True
        elif t.group(2):
            addl = True
        elif vol is None:
            vol = _num(t.group(3))
    return scr_key(year, supp, vol, addl, int(m["page"]))


def stored_citation_key(citation: str) -> tuple | None:
    """Parse a citation FIELD value (`[2006] SUPP. 10 S.C.R. 885`) into the same key shape."""
    m = SCR_RE.search(citation or "")
    return parse_scr(m) if m else None


# --- Neutral citation (the record id itself) --------------------------------------------------------

NEUTRAL_RE = re.compile(
    r"(?<!\d)(?P<year>(?:19|20)\d\d)\s*[:/ ]\s*INSC\s*[:/ ]\s*(?P<n>\d{1,5})(?!\d)"
)


def neutral_case_id(year: int, n: int) -> str:
    return f"{year}_INSC_{n}"


# --- SCC / AIR / SCC OnLine / other reporters (found, not resolved here) ---------------------------------

SCC_RE = re.compile(
    rf"""
    [\[\(]?\s*(?P<year>{_YEAR})\s*[\]\)]?\s*
    (?:(?P<supp>{_SUPP})\s*)?
    (?:\(\s*(?P<pvol>\d{{1,3}})\s*\)\s*)?
    (?:(?P<vol>\d{{1,3}})\s*)?
    (?:(?P<supp2>{_SUPP})\s*)?
    S\s?\.?\s?C\s?\.?\s?C\s?\.?
    (?:\s*\((?:Cri|L\s?&\s?S|Tax|Lab|Cri\.)\))?
    \s*(?P<page>\d{{1,4}})(?!\d)
    """,
    re.I | re.X,
)

SCC_ONLINE_RE = re.compile(
    rf"(?P<year>{_YEAR})\s*SCC\s*On\s?Line\s*(?P<court>[A-Za-z]{{2,6}})\s*(?P<n>\d{{1,6}})",
    re.I,
)

AIR_RE = re.compile(
    rf"""
    A\s?\.?\s?I\s?\.?\s?R\s?\.?\s*[\(\[]?\s*(?P<year>{_YEAR})\s*[\)\]]?\s*
    (?P<court>S\s?\.?\s?C\s?\.?|Supreme\s+Court|[A-Z][A-Za-z]{{1,12}}(?:\s?\([A-Za-z]+\))?)\s*
    (?P<page>\d{{1,4}})(?!\d)
    """,
    re.X,
)

# Other reporters: counted only, to say how much of the citing is outside what can be resolved.
OTHER_RE = re.compile(
    rf"""
    (?:\bJT\s*(?P<jt>{_YEAR})\s*\(\s*\d+\s*\)\s*SC\s*\d+)
    |(?:[\(\[]?{_YEAR}[\)\]]?\s*\(?\d*\)?\s*SCALE\s*\d+)
    |(?:[\(\[]?{_YEAR}[\)\]]?\s*\d*\s*ITR\s*\d+)
    |(?:[\(\[]?{_YEAR}[\)\]]?\s*\d*\s*(?:STC|ELT|LLJ|Comp\.?\s?Cas\.?)\s*\d+)
    |(?:[\(\[]?{_YEAR}[\)\]]?\s*\(?\d*\)?\s*Cri\.?\s?L\.?\s?J\.?\s*\d+)
    """,
    re.I | re.X,
)


def _air_note(court: str) -> str:
    c = re.sub(r"[\s.]", "", court).upper()
    return "air_sc" if c in {"SC", "SUPREMECOURT"} else "air_other_court"


def extract(text: str) -> list[Ref]:
    """Every citation-shaped reference in `text`, in order of position. Overlaps are removed so one
    printed citation is one reference (`AIR 1950 SC 27` is not also an SCR)."""
    found: list[Ref] = []
    for m in SCR_RE.finditer(text):
        key = parse_scr(m)
        if key:
            found.append(Ref("scr", m.group(0).strip(), m.start(), m.end(), key))
    for m in NEUTRAL_RE.finditer(text):
        found.append(
            Ref(
                "neutral",
                m.group(0),
                m.start(),
                m.end(),
                ("neutral", int(m["year"]), int(m["n"])),
            )
        )
    for m in SCC_ONLINE_RE.finditer(text):
        key = ("scc_online", int(m["year"]), m["court"].upper(), int(m["n"]))
        found.append(Ref("scc_online", m.group(0), m.start(), m.end(), key))
    for m in AIR_RE.finditer(text):
        key = (
            "air",
            int(m["year"]),
            re.sub(r"[\s.]", "", m["court"]).upper(),
            int(m["page"]),
        )
        found.append(
            Ref("air", m.group(0), m.start(), m.end(), key, _air_note(m["court"]))
        )
    for m in SCC_RE.finditer(text):
        vol = m["vol"] or m["pvol"]
        key = (
            "scc",
            int(m["year"]),
            bool(m["supp"] or m["supp2"]),
            int(vol) if vol else None,
            int(m["page"]),
        )
        found.append(Ref("scc", m.group(0).strip(), m.start(), m.end(), key))
    for m in OTHER_RE.finditer(text):
        found.append(
            Ref("other_reporter", m.group(0), m.start(), m.end(), ("other", m.group(0)))
        )
    return _drop_overlaps(sorted(found, key=lambda r: (r.start, -(r.end - r.start))))


def _drop_overlaps(refs: list[Ref]) -> list[Ref]:
    out: list[Ref] = []
    for r in refs:
        if out and r.start < out[-1].end:
            continue  # starts inside the previous reference: same printed citation
        out.append(r)
    return out
