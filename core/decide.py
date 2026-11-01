"""Step 3 - Decide (Jev): scope check, filters, safety. Out of scope stops here."""

from __future__ import annotations

import logging
from dataclasses import replace

from adapters.decisions import DecisionUnavailable
from core.contracts import Decision, Deps, Filters, RewrittenQuery

log = logging.getLogger(__name__)


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
    return replace(d, filters=f)
