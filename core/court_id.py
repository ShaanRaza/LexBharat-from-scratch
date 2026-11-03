"""Court from the record id, not from the `court` label (CLAUDE.md section 6).

Plain words: a judgment's record id names its court. Letters then digits (KLHC0103...,
WBCHCA01...) for the courts that have a letter prefix, and <year>_INSC_<n>_<k> for the
country's apex court. Measured across all 32,572,660 judgment rows (3 Nov 2026): 30 prefixes,
each in exactly one source file, so each means exactly one court. The `court` label is less
reliable in a quiet way: 0.58% of rows carry none, 0.21% a spelling variant, and 282 rows
(0.00087%) another court's name. A filter on the label silently drops the first two groups,
which is a recall loss, not a refinement. So the id is trusted and the label is kept beside
it (data/add_court_code.py writes the derived `court_code` into the payload; the label is
never changed or removed, because a few alias labels may be historically real).

Pipeline step touched: 5 (Search): payload filters built in adapters/qdrant.py use this.
Nothing here is a coverage claim: what the product covers is core/coverage.json only. The
table in core/court_ids.json says what the snapshot's ids mean, and is built by
data/build_court_ids.py from measured counts.

Nothing is guessed. An id that matches no prefix has no court (None), and a label that is
generic or shared by two courts is never used to look a court up.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

PATH = Path(__file__).with_name("court_ids.json")

# usual: the court's own spelling. alias: another spelling of the SAME court.
# missing: no label. other_court: the label names a different court than the id does.
# unknown_id: the id matches no known prefix (so nothing can be said).
LabelKind = Literal["usual", "alias", "missing", "other_court", "unknown_id"]


@dataclass(frozen=True)
class CourtId:
    id: str  # the source-file slug, e.g. "kerala"
    label: str  # the court's usual spelling in the `court` field
    aliases: tuple[str, ...]
    codes: tuple[str, ...]  # the id prefixes (payload `court_code` values); INSC for the apex court
    rows: int


@dataclass(frozen=True)
class CourtTable:
    courts: dict[str, CourtId]
    by_code: dict[str, str]  # code -> court id
    sc_pattern: re.Pattern
    sc_code: str
    generic_labels: frozenset[str]  # labels that name no place, never used to look a court up
    totals: dict[str, int]


@lru_cache(maxsize=1)
def load(path: Path = PATH) -> CourtTable:
    raw = json.loads(path.read_text(encoding="utf-8"))
    courts, by_code = {}, {}
    sc_code = None
    pattern = re.compile(raw["supreme_court_id_pattern"])
    for cid, c in raw["courts"].items():
        codes = tuple(c["prefixes"])
        courts[cid] = CourtId(cid, c["label"], tuple(c["aliases"]), codes, c["rows"])
        for code in codes:
            if code in by_code:
                raise ValueError(f"id prefix {code!r} belongs to two courts")
            by_code[code] = cid
        if "INSC" in codes:
            sc_code = "INSC"
    if sc_code is None:
        raise ValueError("the INSC prefix is missing from court_ids.json")
    generic = frozenset(" ".join(g.split()).casefold() for g in raw["generic_labels"])
    return CourtTable(courts, by_code, pattern, sc_code, generic, raw["totals"])


_PREFIX = re.compile(r"^([A-Z]+)\d")


def code_from_record_id(record_id: object) -> str | None:
    """The id prefix that names the court, or None. Never guesses."""
    if not isinstance(record_id, str):
        return None
    t = load()
    if t.sc_pattern.match(record_id):
        return t.sc_code
    m = _PREFIX.match(record_id)
    if m and m.group(1) in t.by_code:
        return m.group(1)
    return None


def court_from_record_id(record_id: object) -> CourtId | None:
    code = code_from_record_id(record_id)
    return load().courts[load().by_code[code]] if code else None


def court(court_id: str) -> CourtId:
    return load().courts[court_id]  # KeyError for a court nobody registered


def _norm(label: str) -> str:
    return " ".join(label.split()).casefold()


@lru_cache(maxsize=1)
def _lookup() -> dict[str, str | None]:
    """label -> court id, for labels that name exactly ONE court. A label shared by two
    courts, or one that names no place (listed as generic in the table), maps to None: ambiguous."""
    seen: dict[str, set[str]] = {}
    for c in load().courts.values():
        for lab in (c.label, *c.aliases):
            seen.setdefault(_norm(lab), set()).add(c.id)
    generic = load().generic_labels
    return {
        k: (next(iter(v)) if len(v) == 1 and k not in generic else None)
        for k, v in seen.items()
    }


def court_for_label(label: object) -> CourtId | None:
    """Look a court up by a label a user or a payload uses. None when the label is
    unknown, generic or shared by two courts: the caller then applies no court filter
    instead of the wrong one."""
    if not isinstance(label, str) or not label.strip():
        return None
    cid = _lookup().get(_norm(label))
    return load().courts[cid] if cid else None


def classify_label(record_id: object, label: object) -> LabelKind:
    """How a stored `court` label relates to the court the id names."""
    c = court_from_record_id(record_id)
    if c is None:
        return "unknown_id"
    if not isinstance(label, str) or not label.strip():
        return "missing"
    if label == c.label:
        return "usual"
    if _norm(label) in {_norm(a) for a in c.aliases}:
        return "alias"
    return "other_court"
