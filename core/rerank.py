"""Step 6 - RE-RANK: Voyage rerank-2.5-lite keeps the best 10 of the 50."""

from __future__ import annotations

from adapters.voyage import VoyageClient, VoyageUnavailable
from core.constants import RERANK_TOP_K
from core.models import RankedPassage, RerankResult, SearchResult


async def rerank(
    query: str,
    found: SearchResult,
    voyage: VoyageClient,
    *,
    top_k: int = RERANK_TOP_K,
) -> RerankResult:
    hits = list(found.hits)
    if not hits:
        return RerankResult(passages=())
    try:
        ranked = await voyage.rerank(query, [h.text for h in hits], top_k)
        chosen = [(hits[r.index], r.score) for r in ranked]
        used_fallback = False
    except VoyageUnavailable:
        # Keep the search order; the gate still filters, the verifier still checks.
        chosen = [(h, h.score) for h in hits[:top_k]]
        used_fallback = True
    passages = tuple(
        RankedPassage(h.record_id, h.chunk_id, h.text, score, rank=i + 1)
        for i, (h, score) in enumerate(chosen)
    )
    return RerankResult(passages=passages, used_fallback=used_fallback)
