"""Step 6 - Re-rank: Voyage rerank-2.5-lite keeps the top 10."""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Sequence

from adapters.voyage import VoyageUnavailable
from core.contracts import RERANK_TOP_K, Deps, Passage, RewrittenQuery

log = logging.getLogger(__name__)


async def rerank(
    rq: RewrittenQuery, passages: Sequence[Passage], deps: Deps
) -> tuple[Passage, ...]:
    """Input: up to 50 passages. Output: at most 10, best first. If Voyage is down we
    keep the search order (already sorted by score)."""
    if not passages:
        return ()
    try:
        ranked = await deps.reranker.rerank(
            rq.query, [p.text for p in passages], RERANK_TOP_K
        )
    except VoyageUnavailable:
        log.warning("rerank down; keeping search order")
        return tuple(passages[:RERANK_TOP_K])
    return tuple(
        dataclasses.replace(passages[i], score=s) for i, s in ranked[:RERANK_TOP_K]
    )
