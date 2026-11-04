"""Step 3 - Decide (Jev): scope check, filters, safety. Out of scope stops here."""

from __future__ import annotations

import logging
import re
from dataclasses import replace

from adapters.decisions import DecisionUnavailable
from core.act_ids import year_names_an_act
from core.contracts import Decision, Deps, Filters, RewrittenQuery

log = logging.getLogger(__name__)


def _section_is_in_query(section: str, query: str) -> bool:
    """True if the section's number is written in the query ("section 438", "s. 65B").

    Only the digits are compared: "156(3)" and "65B" count as present when 156 / 65
    stands alone in the query."""
    m = re.match(r"\s*(\d+)", str(section))
    return bool(m) and re.search(rf"(?<![\d.]){m.group(1)}(?!\d)", query) is not None


async def decide(rq: RewrittenQuery, deps: Deps, *, uploads: bool = False) -> Decision:
    """Input: RewrittenQuery. Output: Decision.

    Only the user's question text goes to the decision layer. If every decider is down
    we keep going as in-scope (the gate and verifier still protect the answer) but treat
    the safety class as personal_advice, which only makes the disclaimer stronger.
    """
    try:
        d = await deps.decisions.decide(rq.query, uploads=uploads)
    except DecisionUnavailable:
        log.warning("decision layer unavailable; conservative default")
        d = Decision("in_scope", Filters(), "personal_advice", (), False)
    f = d.filters
    f = replace(
        f,
        act=f.act or rq.act,
        section=f.section or rq.section,
        case_number=f.case_number or rq.case_number,
        year_from=f.year_from or rq.year,
        year_to=f.year_to or rq.year,
    )

    # A year that is part of an Act's name ("CrPC 1973") dates the Act, not the
    # judgments wanted. Whoever supplied it (the decider, the rewrite step, the
    # regex fallback), it never becomes a judgment-year filter.
    def _own(y: int | None) -> int | None:
        return None if year_names_an_act(rq.query, y, f.act, f.act_year) else y

    f = replace(f, year_from=_own(f.year_from), year_to=_own(f.year_to))

    # A section the user did not name must not become a filter. The decider guesses one
    # for a research question ("res judicata" -> 11, "temporary injunction" -> 39, which
    # is an Order); search then hard-filters on the guess, which strips every judgment
    # from the answer (17 of 17 answered questions in the 100-question run kept statute
    # text only). rq.query is the standalone rewrite, so a section the user named, in
    # this turn or an earlier one, is in it. Whoever supplied the section (decider,
    # rewrite, regex), it stays only if its number is written there.
    if f.section and not _section_is_in_query(f.section, rq.query):
        f = replace(f, section=None)
    return replace(d, filters=f)
