"""Citator Phase 1: the SCC and AIR to top-court record map, and the rule that decides what to trust.

Plain words: a top-court reporter headnote lists the cases a judgment relies on, each with two
citations joined by a colon: `(2002) 5 SCC 1 : [2002] 3 SCR 810`. The SCR side is one of our records,
so the pair says "this SCC citation is that record". One judgment may print a pair wrongly (an OCR slip,
a typo). A pair printed by several judgments that have nothing to do with each other is far safer.

The rule (owner-approved scope, DATA-GAPS 23.14, validated against the Judges Library table of 64
landmark cases: 47 right, 0 wrong, 13 not covered; trusting a lone pair was not validated and is out):

  a citation is mapped to a record only if the winning record is printed by at least 2 distinct
  judgments AND by at least twice as many as any other record that citation was paired with.

Independence: evidence is a set of citing judgment ids per (citation, record), so one judgment printing
a pair ten times counts once. A judgment's own pair is removed by the caller, because a judgment saying
what its own citation is carries no independent information.

Pipeline: none of the 11 steps. This is offline data work. It touches no verifier check.
"""

# ruff: noqa: E501  (prose docstring)
from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping

MIN_INDEPENDENT_CASES = (
    2  # the winner must be printed by at least this many distinct judgments
)
DOMINANCE = 2  # and by at least this many times the runner-up


def trusted_target(evidence: Mapping[str, Iterable[str]]) -> str | None:
    """`evidence` is {record id: judgments that printed this citation paired with that record}.
    Returns the record to map the citation to, or None when the evidence does not meet the rule."""
    support = sorted(
        ((len(set(citing)), rec) for rec, citing in evidence.items()), reverse=True
    )
    support = [s for s in support if s[0] > 0]
    if not support:
        return None
    top, record = support[0]
    runner_up = support[1][0] if len(support) > 1 else 0
    if top >= MIN_INDEPENDENT_CASES and top >= DOMINANCE * runner_up:
        return record
    return None


def build_map(
    pairs: Mapping[Hashable, Mapping[str, Iterable[str]]],
    *,
    air_courts: frozenset[str] = frozenset({"SC"}),
) -> dict[Hashable, str]:
    """{citation key: record id} for every key whose evidence passes `trusted_target`.

    Keys are the tuples `core.citator.refs` makes: ("scc", year, supp, vol, page) and
    ("air", year, court, page). An AIR citation of a regional court is never mapped: the record it would
    name is a top-court record, and an AIR regional-court key would be a different case."""
    out: dict[Hashable, str] = {}
    for key, evidence in pairs.items():
        if (
            isinstance(key, tuple)
            and key
            and key[0] == "air"
            and key[2] not in air_courts
        ):
            continue
        record = trusted_target(evidence)
        if record is not None:
            out[key] = record
    return out
