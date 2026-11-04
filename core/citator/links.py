"""Citator Phase 1: the data model for "which Supreme Court judgments cite this one".

Plain words: this module can say how many judgments in our data cite a case in a form we can read,
and who they are. It cannot say anything about whether the case is still good law, because there is
no field that could hold that. That is the design rule: the confident wording is impossible to build.

  * A `Link` is one fact: judgment A printed a reference to judgment B. It carries no treatment
    (followed, overruled, doubted). Reading the editor's word is Phase 2 and needs an advocate.
  * `InboundLinks` is the list of links into one case. The ONLY words it can produce come from
    `describe()`. A count of 0 reads "no judgment in our data cites this case in a form we can read",
    which is a limit of our data and never clearance. The count is a floor: a case cited only in SCC
    form, with no pair printed anywhere, has 0 here however often it is cited (DATA-GAPS 23.10, 23.14).
  * There is deliberately no `status`, `is_good_law`, `cleared` or `treatment` attribute anywhere in
    this module, and `tests/citator/test_links.py` fails if one appears or if any sentence `describe()`
    can return reads as clearance.

Pipeline: none of the 11 steps. This is offline data work. It touches no verifier check.
"""

# ruff: noqa: E501  (prose docstring)
from __future__ import annotations

import gzip
import json
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Via(StrEnum):
    """How a reference was tied to the cited record."""

    DIRECT = "direct"  # an SCR or neutral citation that equals a stored record
    MAPPED = "mapped"  # an SCC or AIR citation placed through the headnote pair map


@dataclass(frozen=True, slots=True)
class Link:
    """Judgment `citing` printed a reference to judgment `cited`. Nothing about what it said."""

    citing: str  # record id, e.g. 2018_INSC_329
    cited: str
    via: Via
    mentions: int = 1  # times the reference is printed in the citing judgment

    def __post_init__(self) -> None:
        if self.citing == self.cited:
            raise ValueError("a judgment citing itself is not a link")
        if self.mentions < 1:
            raise ValueError("a link needs at least one printed mention")


# The two sentences. Everything a screen or an API may say about inbound links is one of these, so
# a reviewer can read the whole vocabulary here. Neither says "good law", "clear" or "not cited".
ZERO_READABLE = (
    "No judgment in our data cites this case in a form we can read. "
    "That is a limit of our data, not a finding about the case."
)
SOME_READABLE = (
    "{n} judgment{s} in our data cite{v} this case in a form we can read. "
    "This is a minimum, not a full count, and it does not say whether any of them follows, "
    "distinguishes or overrules it."
)


@dataclass(frozen=True, slots=True)
class InboundLinks:
    """Every link into one case that we could read. Immutable; `readable` is a floor."""

    case_id: str
    links: tuple[Link, ...]

    def __post_init__(self) -> None:
        for link in self.links:
            if link.cited != self.case_id:
                raise ValueError(f"link into {link.cited} filed under {self.case_id}")
        if len({link.citing for link in self.links}) != len(self.links):
            raise ValueError("one link per citing judgment")

    @property
    def readable(self) -> int:
        """Distinct judgments that cite this case in a form we can read. A floor, never a total."""
        return len(self.links)

    @property
    def citing(self) -> tuple[str, ...]:
        return tuple(sorted(link.citing for link in self.links))

    def describe(self) -> str:
        n = self.readable
        if n == 0:
            return ZERO_READABLE
        return SOME_READABLE.format(
            n=n, s="" if n == 1 else "s", v="s" if n == 1 else ""
        )


def group_inbound(links: Iterable[Link]) -> dict[str, InboundLinks]:
    """One `InboundLinks` per cited case that has at least one link. A case absent from the result
    has none we can read; use `inbound_for` so that absence becomes a described zero."""
    by_cited: dict[str, dict[str, Link]] = {}
    for link in links:
        slot = by_cited.setdefault(link.cited, {})
        prev = slot.get(link.citing)
        if prev is None or (prev.via is Via.MAPPED and link.via is Via.DIRECT):
            slot[link.citing] = (
                link  # a direct reading beats a mapped one for the same pair
            )
    return {c: InboundLinks(c, tuple(s.values())) for c, s in by_cited.items()}


def inbound_for(case_id: str, grouped: dict[str, InboundLinks]) -> InboundLinks:
    return grouped.get(case_id) or InboundLinks(case_id, ())


SC_LINKS = (
    Path(__file__).resolve().parents[2] / "data" / "citator" / "sc_links.jsonl.gz"
)


def load_links(path: Path = SC_LINKS) -> list[Link]:
    """The built Supreme Court links (scan/sc/build_links.py), one `Link` per line."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [
            Link(r["citing"], r["cited"], Via(r["via"]), r["mentions"])
            for r in map(json.loads, f)
        ]
