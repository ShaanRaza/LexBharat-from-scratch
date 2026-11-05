"""Step 7 of 11: the answer-or-refuse gate.

Plain words: the re-ranker hands us up to 10 passages. We ask Jev (through
deps.decisions) to rate each one: answers the question / partly / not relevant.
Not-relevant passages are dropped. If nothing clears the threshold (0.6, from
settings) we return an EMPTY result, and the pipeline tells the user "not found" and
writes nothing. Whatever survives (at most 8) is labelled S1..S8, best first. Those
labels are what the verifier later checks citations against (check 1).

Fixed numbers 50 -> 10 -> 8 and the threshold live in core.contracts / settings; this
file never hard-codes them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import replace

from adapters.decisions import DecisionUnavailable
from core.contracts import (
    GATE_MAX_PASSAGES,
    RERANK_TOP_K,
    Deps,
    GateResult,
    Passage,
    Rating,
    RewrittenQuery,
)


async def _rate_one(
    query: RewrittenQuery, passage: Passage, deps: Deps
) -> tuple[Rating, float]:
    """Ask the decision adapter; if it cannot answer, use the re-ranker's score.

    Trade-off: with Jev down we still gate, using the rerank score against the same
    threshold, instead of passing everything through (would weaken the gate) or
    refusing everything (would make a Jev outage a full outage).
    """
    try:  # the adapter itself picks Jev or the Gemini fallback from the switches
        return await deps.decisions.rate_passage(query.query, passage)
    except (DecisionUnavailable, TimeoutError):  # no decider -> rerank score
        return "partly", passage.score


async def gate(
    query: RewrittenQuery, passages: Sequence[Passage], deps: Deps
) -> GateResult:
    """Rate, drop, threshold, cap at 8, label S1..S8."""
    threshold = deps.settings.JEV_GATE_THRESHOLD
    candidates = list(passages)[:RERANK_TOP_K]
    rated = await asyncio.gather(*(_rate_one(query, p, deps) for p in candidates))

    ratings: dict[str, Rating] = {
        p.record_id: r for p, (r, _) in zip(candidates, rated)
    }
    kept = [
        (p, score)
        for p, (rating, score) in zip(candidates, rated)
        if rating != "not_relevant" and score >= threshold
    ]
    if not kept:
        return GateResult(passages=(), confidence=0.0, ratings=ratings)

    kept.sort(key=lambda ps: ps[1], reverse=True)  # stable: ties keep rerank order
    kept = kept[:GATE_MAX_PASSAGES]
    labelled = tuple(
        replace(p, source_id=f"S{i}", score=score)
        for i, (p, score) in enumerate(kept, start=1)
    )
    return GateResult(
        passages=labelled,
        confidence=max(score for _, score in kept),
        ratings=ratings,
    )
