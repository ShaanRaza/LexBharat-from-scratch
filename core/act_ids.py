"""Acts by name, sections by shape, and which years are an Act's own (steps 3 and 5).

The decision layer returns an Act as text ("Code of Criminal Procedure, 1973") and a
section as text ("438", "Article 21", "Order VII Rule 11"). Step 5 needs two things
it did not have:

* Which stored Act is that? `resolve_act` maps the name to the Act id(s) of the
  served collection, from the index in `core/act_ids.json` (built by
  `data/build_act_ids.py`). A name that does not resolve is NOT guessed.
* Is the "section" a plain section number, one a stored Act can carry?
  `plain_section` says. "Article 21" and "Order VII Rule 11" are not, so they never
  become a hard payload filter.

And one thing step 3 needs: a year inside an Act's name ("CrPC 1973") dates the Act,
not the judgments the user wants. `year_names_an_act` says when a year is that.
Without it the year became a filter on judgments and the answer was "nothing found".

Nothing here claims what the product covers (core/coverage.json is the only source
for that); the index lists what is stored, no more.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).with_name("act_ids.json")

_YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b")
_NUMBERED = re.compile(r"\b\d+[a-z]?\s+of\s+(?:1[89]|20)\d\d\b")  # "45 of 1860"
_REPEAL_NOTE = re.compile(r"\(rep[^)]*\)")

# Abbreviations lawyers use for an Act. Each maps to a title key and the year that
# tells one Act of that name from another; resolve_act still looks the result up in
# the index, so an Act the data does not hold stays unresolved.
ALIASES: dict[str, tuple[str, int]] = {
    "crpc": ("code of criminal procedure", 1973),
    "cr pc": ("code of criminal procedure", 1973),
    "cpc": ("code of civil procedure", 1908),
    "ipc": ("indian penal code", 1860),
    "iea": ("indian evidence act", 1872),
    "bns": ("bharatiya nyaya sanhita", 2023),
    "bnss": ("bharatiya nagarik suraksha sanhita", 2023),
    "bsa": ("bharatiya sakshya adhiniyam", 2023),
    "ni act": ("negotiable instruments act", 1881),
    "it act": ("information technology act", 2000),
    "ibc": ("insolvency and bankruptcy code", 2016),
    "pmla": ("prevention of money laundering act", 2002),
    "ndps": ("narcotic drugs and psychotropic substances act", 1985),
    "pocso": ("protection of children from sexual offences act", 2012),
    "rti act": ("right to information act", 2005),
}

# A year printed after an Act's name belongs to the name: the word Act, Code, Sanhita,
# Adhiniyam or Ordinance, then up to five more title words (of, and, the, for, or a
# Capitalised word), then the year ("Contract Act, 1872", "Code of Criminal
# Procedure, 1973", "Nyaya Sanhita, 2023"). A year after "in", "after", "since" or
# "decided" does not match, because those are not title words.
_ACT_THEN_YEAR = re.compile(
    r"(?i:\b(?:act|acts|code|sanhita|adhiniyam|ordinance)\b)"
    r"(?:[\s,.\-:]+(?:(?i:of|and|the|for)|[A-Z][A-Za-z\-]*)){0,5}"
    r"[\s,.\-:]*(?i:(?:no\.?\s*\d+[a-z]?\s*of\s*)?(?:of\s+)?)"
    r"(1[89]\d\d|20\d\d)\b"
)
# "CrPC 1973", "IPC 1860", "BNSS 2023": a short abbreviation, then the year.
_ABBREVIATION_THEN_YEAR = re.compile(r"\b([A-Za-z]{2,6})[\s,.\-:]+(1[89]\d\d|20\d\d)\b")
_PLAIN_SECTION = re.compile(r"^\d+[A-Za-z]{0,2}$")


def norm_key(name: str | None) -> str:
    """A title as words: lower case, no "The", no repeal note, no "45 of 1860", no
    year, no punctuation."""
    t = _REPEAL_NOTE.sub(" ", (name or "").lower())
    t = _NUMBERED.sub(" ", t)
    t = _YEAR.sub(" ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[4:] if t.startswith("the ") else t


def name_year(name: str | None) -> int | None:
    """The year printed in an Act's name (the last one), None if there is none."""
    years = _YEAR.findall(_REPEAL_NOTE.sub(" ", _NUMBERED.sub(" ", name or "")))
    return int(years[-1]) if years else None


@dataclass(frozen=True)
class ActIndex:
    # key -> ((act_id, year, status), ...)
    by_key: dict[str, tuple[tuple[str, int | None, str], ...]]

    @classmethod
    def from_records(cls, records) -> ActIndex:
        by: dict[str, list] = {}
        for act_id, title, year, status in records:
            y = int(year) if str(year).isdigit() else None
            by.setdefault(norm_key(title), []).append((act_id, y, status or ""))
        return cls({k: tuple(v) for k, v in by.items()})

    def resolve(self, name: str | None) -> tuple[str, ...]:
        """The Act id(s) the name stands for, or () when it does not resolve. Never a
        guess: a name with no year that fits two different Acts, or a year the index
        does not hold, is unresolved."""
        if not name or not name.strip():
            return ()
        key, year = norm_key(name), name_year(name)
        alias = ALIASES.get(re.sub(r"[^a-z ]+", " ", name.lower()).strip())
        if alias:
            key, year = alias
        cands = self.by_key.get(key, ())
        if year is not None:
            cands = tuple(c for c in cands if c[1] == year)
        elif len({c[1] for c in cands}) > 1:
            in_force = tuple(c for c in cands if c[2] == "in_force")
            if len({c[1] for c in in_force}) != 1:
                return ()  # no year and two Acts of that name: cannot tell which
            cands = in_force
        if not cands:
            return ()
        # a repealed twin of the same name is not the target
        live = tuple(c for c in cands if c[2] == "in_force")
        return tuple(sorted({c[0] for c in (live or cands)}))


@lru_cache(maxsize=1)
def load_index(path: Path = PATH) -> ActIndex:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ActIndex.from_records(data["acts"])


def resolve_act(name: str | None) -> tuple[str, ...]:
    return load_index().resolve(name)


def plain_section(section: str | None) -> str | None:
    """ "438" -> "438", "Section 65B" -> "65B", "156(3)" -> "156" (the stored number
    has no sub-section). None for anything that is not a plain section number:
    "Article 21", "Order VII Rule 11", "Rule 3"."""
    if not section:
        return None
    s = re.sub(
        r"^(?:sections?|secs?\.?|s\.)\s*", "", section.strip(), flags=re.IGNORECASE
    )
    s = re.sub(r"(\s*\([0-9A-Za-z]+\))+$", "", s).strip()  # 156(3), 41(1)(b)
    return s.upper() if _PLAIN_SECTION.match(s) else None


def year_names_an_act(
    text: str, year: int | None, act: str | None = None, act_year: int | None = None
) -> bool:
    """True when `year` is part of an Act's name, not a date to take judgments from.

    It is, when: the decider said so (`act_year`); the year is in the Act's name
    ("Code of Criminal Procedure, 1973"); the text prints it right after Act, Code,
    Sanhita or Adhiniyam ("Contract Act, 1872"); or, once an Act has been identified,
    right after an abbreviation of it ("CrPC 1973"). A year after "after", "since",
    "in" or "decided" is none of these and stays."""
    if not year:
        return False
    if act_year and year == act_year:
        return True
    if act and str(year) in act:
        return True
    for m in _ACT_THEN_YEAR.finditer(text or ""):
        if int(m.group(1)) == year:
            return True
    if act or act_year:
        for m in _ABBREVIATION_THEN_YEAR.finditer(text or ""):
            word = m.group(1)
            has_inner_capital = any(c.isupper() for c in word[1:]) or word.isupper()
            if int(m.group(2)) == year and has_inner_capital:
                return True
    return False
