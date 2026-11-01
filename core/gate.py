"""Step 7 - GATE (Jev): rate every passage, keep at most 8 labelled S1..S8.

A passage survives if it is rated "answers" or "partly" with confidence >= the threshold
(settings.JEV_GATE_THRESHOLD, 0.6). If none survive the user gets "not found" and no
answer is written. All passages are rated at once (asyncio.gather).
If neither Jev nor the fallback can rate, DecisionUnavailable is raised: we fail closed
rather than let unrated passages through.
"""

from __future__ import annotations

import asyncio

from adapters.jev import DecisionAdapter
from core.constants import MAX_PASSAGES
from core.models import GateResult, RerankResult, Source
from core.settings import Settings


async def gate(
    query: str,
    reranked: RerankResult,
    decisions: DecisionAdapter,
    settings: Settings,
    *,
    is_upload_chat: bool = False,
) -> GateResult:
    passages = reranked.passages
    ratings = await asyncio.gather(
        *(
            decisions.relevance(query, p.text, contains_upload_text=is_upload_chat)
            for p in passages
        )
    )
    survivors = []
    jev_used = False
    for passage, rating in zip(passages, ratings, strict=True):
        jev_used = jev_used or rating.source == "jev"
        if rating.choice == "not_relevant":
            continue
        if rating.confidence < settings.JEV_GATE_THRESHOLD:
            continue
        survivors.append((passage, rating))

    sources = tuple(
        Source(
            source_id=f"S{i + 1}",
            record_id=p.record_id,
            chunk_id=p.chunk_id,
            text=p.text,
            rank=p.rank,
            rerank_score=p.rerank_score,
            relevance=r.choice,
            relevance_confidence=r.confidence,
        )
        for i, (p, r) in enumerate(survivors[:MAX_PASSAGES])
    )
    return GateResult(sources=sources, jev_used=jev_used)
