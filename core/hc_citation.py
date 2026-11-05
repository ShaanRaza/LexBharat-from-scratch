"""Identifiers for judgments that have no stored citation string (A124).

The dataset stores a citation string for most judgments and for none of the regional
ones (CLAUDE.md section 6). Two things can stand in for it. They are KEPT APART
from `citation_string` and from each other, because they are different kinds of claim:

  neutral citation  a PUBLISHED citation the court itself printed on the judgment, such
                    as 2023:DHC:1234. Extracted from the judgment's own header, and only
                    kept if three guards all agree (below). It is not retyped.
  case reference    a LABEL built from three stored fields, "CRL.A. 123/2019, <court>,
                    decided 4 March 2021". It is a description of the record, never
                    shaped like a published citation, and it is never emitted when any
                    field is missing or looks like garbage.

THE TRAP. A judgment's text cites other cases, so the first neutral citation in the
text is often not this judgment's own. Attaching another case's citation to a record is
worse than showing none, so a candidate is rejected unless ALL of these hold:
  1. it sits in the header region (the first HEADER_CHARS characters), never the body;
  2. its year equals the year of decision_date;
  3. its court code belongs to the record's court (core/neutral_citation_courts.json).
Any disagreement is a rejection with a named reason, never a guess. Two different
neutral citations in the header are also a rejection (which one is ours?).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

HEADER_CHARS = 800  # the header region; a design constant, to be tuned on real headers
_COURTS_FILE = Path(__file__).with_name("neutral_citation_courts.json")

# 2023:DHC:1234   2022:KER:5678   2023:AHC-LKO:123   2023:DHC:1234-DB
NEUTRAL = re.compile(
    r"(?<![\w:])((?:19|20)\d{2}):([A-Z]{2,8}(?:-[A-Z]{2,6})?):(\d{1,7})(?:-[A-Z]{2,4})?"
    r"(?![\w:])"
)
# Anything a reporter citation could look like. A case reference is refused if a stored
# field makes it look like one.
_REPORTER_LOOK = re.compile(
    r"\b(?:AIR|SCC|SCR|SCALE|ILR|MANU|INSC|SCC\s*ONLINE)\b|^\s*\d{4}\s+[A-Za-z.]+\s+\d+\s*$"
    r"|\[\d{4}\]|\(\d{4}\)\s*\d",
    re.IGNORECASE,
)
_MONTHS = (
    "January February March April May June July August September October November "
    "December"
).split()


# --- Dates ----------------------------------------------------------------------------
def parse_date(raw: Any) -> date | None:
    """DD-MM-YYYY (as the dataset stores it), YYYY-MM-DD, or DD/MM/YYYY."""
    s = str(raw or "").strip()
    for pat, order in (
        (r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", "dmy"),
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", "ymd"),
    ):
        m = re.fullmatch(pat, s[:10] if order == "ymd" else s)
        if m:
            a, b, c = (int(g) for g in m.groups())
            d, mo, y = (a, b, c) if order == "dmy" else (c, b, a)
            try:
                got = date(y, mo, d)
            except ValueError:
                return None
            return got if 1900 <= got.year <= 2100 else None
    return None


# --- 1. Neutral citation, extracted and guarded ---------------------------------------
@dataclass(frozen=True)
class NeutralResult:
    citation: str | None
    reason: str  # "ok" or why it was rejected; the data session counts these


@lru_cache(maxsize=1)
def _courts() -> dict[str, Any]:
    """Fails closed: a missing table raises, so no citation is accepted without a check
    of the court."""
    try:
        data = json.loads(_COURTS_FILE.read_text(encoding="utf-8"))
        codes = {k.upper(): [t.lower() for t in v] for k, v in data["codes"].items()}
        must = str(data["court_must_contain"]).lower()
    except (OSError, KeyError, ValueError, AttributeError) as e:
        raise RuntimeError(f"{_COURTS_FILE.name} is missing or unreadable") from e
    if not codes:
        raise RuntimeError(f"{_COURTS_FILE.name} has no codes")
    return {"codes": codes, "must": must}


def court_matches(code: str, court: str | None) -> bool | None:
    """True / False when the code is known; None when the code is not in the table."""
    table = _courts()
    tokens = table["codes"].get(code.split("-")[0].upper())
    if tokens is None:
        return None
    low = (court or "").lower()
    return table["must"] in low and all(t in low for t in tokens)


def extract_neutral_citation(
    text: str,
    court: str | None,
    decision_date: Any,
    header_chars: int = HEADER_CHARS,
) -> NeutralResult:
    """The judgment's own neutral citation, or None with the reason it was refused.

    `text` must START at the first character of the judgment: a chunk from the middle
    has no header, so the caller must not pass one."""
    header, rest = text[:header_chars], text[header_chars:]
    found = {m.group(0): m for m in NEUTRAL.finditer(header)}
    if not found:
        # Only worth knowing for the count: the trap is a citation in the body.
        return NeutralResult(
            None, "body_only" if NEUTRAL.search(rest) else "no_candidate"
        )
    if len(found) > 1:
        return NeutralResult(None, "ambiguous")
    (cit, m), *_ = found.items()
    when = parse_date(decision_date)
    if when is None:
        return NeutralResult(None, "no_date")
    if int(m.group(1)) != when.year:
        return NeutralResult(None, "year_mismatch")
    if not (court or "").strip():
        return NeutralResult(None, "no_court")
    ok = court_matches(m.group(2), court)
    if ok is None:
        return NeutralResult(None, "unknown_court_code")
    if not ok:
        return NeutralResult(None, "court_mismatch")
    return NeutralResult(cit, "ok")


# --- 2. Case reference, built from fields --------------------------------------------
def _usable_case_number(raw: Any) -> str | None:
    s = " ".join(str(raw or "").split())
    if not 3 <= len(s) <= 60 or len(s.split()) > 8:
        return None
    if not (re.search(r"\d", s) and re.search(r"[A-Za-z]", s)):
        return None
    if NEUTRAL.search(s) or _REPORTER_LOOK.search(s):
        return None  # a stored field that already looks like a citation: say nothing
    return s


def _usable_court(raw: Any) -> str | None:
    s = " ".join(str(raw or "").split())
    if not 3 <= len(s) <= 80 or not re.search(r"[A-Za-z]", s) or re.search(r"\d", s):
        return None
    return s


def case_reference(case_number: Any, court: Any, decision_date: Any) -> str | None:
    """'CRL.A. 123/2019, <court>, decided 4 March 2021', or None unless all three fields
    are present and usable. The shape (a comma list ending in 'decided <date>') is
    deliberately unlike any reporter citation."""
    num, name, when = (
        _usable_case_number(case_number),
        _usable_court(court),
        parse_date(decision_date),
    )
    if not (num and name and when):
        return None
    return f"{num}, {name}, decided {when.day} {_MONTHS[when.month - 1]} {when.year}"
